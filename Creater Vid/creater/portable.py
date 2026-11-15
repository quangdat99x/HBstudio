"""Projects that move between machines: the same folder layout everywhere (<data>\\VideoLab\\creater-projects\\<slug>),
stored folders that follow the projects root, and project folders copied in from another machine registered by
themselves from their project.json.

- relocate_db: projects.dir of a project whose folder now lives under this machine's projects root is pointed there.
- import_new_projects: a folder with a project.json that no project of this database uses becomes a project (title,
  topic, settings and step statuses from project.json; the chat history stays on the machine it was made on).
- ProjectScanner: does both at startup and then once a minute (only a listing of the root: cheap).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path

from . import config, db, store, workflow
from .util import now_iso

log = logging.getLogger("creater.portable")
MACHINE = os.environ.get("COMPUTERNAME") or "may-nay"

_RX = re.compile(r"(?<![A-Za-z0-9_])(?P<pre>[A-Za-z]:(?P<sep>\\\\|\\|/)[^\"\r\n\t:*?<>|`]*?creater-projects)"
                 r"(?=(?P=sep)|\"|$)", re.I)


def rebase_text(text, root=None):
    if not isinstance(text, str) or "creater-projects" not in text.lower():
        return text
    new = str(root or store.root()).rstrip("\\/")

    def sub(m):
        sep, pre = m.group("sep"), m.group("pre")
        target = new.replace("\\", "/") if sep == "/" else new.replace("\\", sep)
        return pre if pre.lower() == target.lower() else target
    return _RX.sub(sub, text)


def relocate_db() -> int:
    """projects.dir outside this machine's projects root, whose folder is in the root: point it there (the folder in
    the current data root wins even when the old one still exists, e.g. after copying rather than moving)."""
    root = store.root()
    moved: list[int] = []
    for p in db.rows("SELECT id, dir FROM projects"):
        cur = Path(p["dir"])
        try:
            if cur.parent.resolve() == root.resolve():
                continue
        except OSError:
            pass
        new = rebase_text(p["dir"], root)
        if new == p["dir"]:
            candidate = root / cur.name                # a folder that never sat under creater-projects
            new = str(candidate) if candidate.is_dir() else p["dir"]
        if new != p["dir"] and Path(new).is_dir():
            with db.tx() as c:
                c.execute("UPDATE projects SET dir=? WHERE id=?", (new, p["id"]))
            moved.append(p["id"])
    if moved:
        log.info("relocate: %d project folders now under %s", len(moved), root)
        for pid in moved:                              # only the moved projects: their project.json names the folder
            try:
                store.write_brief(store.get_project(pid))
            except Exception:  # noqa: BLE001
                log.exception("write_brief %s", pid)
    return len(moved)


_ACTIVE = ("queued", "running")


def import_new_projects() -> list[dict]:
    """Register project folders copied in from another machine (each has its project.json)."""
    root = store.root()
    if not root.is_dir():
        return []
    known = {str(Path(r["dir"])).lower() for r in db.rows("SELECT dir FROM projects")}
    slugs = {r["slug"] for r in db.rows("SELECT slug FROM projects")}
    added = []
    for d in sorted(root.iterdir()):
        pj = d / "project.json"
        if not d.is_dir() or str(d).lower() in known or not pj.is_file():
            continue
        try:
            info = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("project.json unreadable in %s: %s", d, e)
            continue
        kind = info.get("kind") if info.get("kind") in config.KINDS else "doc"
        slug = d.name if d.name not in slugs else info.get("slug") or d.name
        if slug in slugs:                                # same slug, other folder: keep both, name by the folder
            slug = f"{d.name}-{MACHINE.lower()}"
        topic = (info.get("topic") or info.get("title") or d.name).strip()
        now = now_iso()
        yt = info.get("youtube") or {}
        with db.tx() as c:
            c.execute("""INSERT INTO projects(kind, slug, title, topic, brief, language, audience, style, format,
                         target_sec, budget_usd, use_jre, auto_advance, pipeline, yt_channel, dir, created_at, updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (kind, slug, (info.get("title") or topic).strip(), topic, info.get("brief"), info.get("language"),
                       info.get("audience"), info.get("style"), info.get("format") or "16:9", info.get("target_sec"),
                       info.get("budget_usd"), 1 if info.get("use_jre_highlights") else 0,
                       1 if info.get("auto_advance") else 0, info.get("pipeline") if kind == "doc" else None,
                       yt.get("channel_id"), str(d), now, now))
            pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            steps = info.get("steps") or {}
            keys = workflow.flow(kind).keys
            for i, key in enumerate(keys):
                st = steps.get(key) or ("ready" if i == 0 else "locked")
                if st in _ACTIVE:                        # a run of the other machine cannot continue here
                    st = "ready"
                c.execute("INSERT OR IGNORE INTO project_steps(project_id, step, status) VALUES(?,?,?)", (pid, key, st))
        slugs.add(slug)
        p = store.get_project(pid)
        store.write_brief(p)
        store.log_event(pid, "imported", f"nạp dự án chép từ máy khác: {d.name}")
        added.append({"id": pid, "slug": slug, "title": p["title"], "dir": str(d)})
    if added:
        log.info("imported %d copied projects: %s", len(added), ", ".join(a["slug"] for a in added))
        try:
            from . import notify
            notify.notify("done", f"Đã nạp {len(added)} dự án chép vào",
                          ", ".join(a["title"] for a in added)[:300], "/")
        except Exception:  # noqa: BLE001
            log.exception("notify")
    return added


class ProjectScanner(threading.Thread):
    def __init__(self, interval: int = 60):
        super().__init__(name="creater-project-scanner", daemon=True)
        self.interval = interval
        self._stop = threading.Event()
        self._last_listing = None

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                root = store.root()
                listing = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
                if listing != self._last_listing:
                    relocate_db()
                    import_new_projects()
                    self._last_listing = listing
            except Exception:  # noqa: BLE001
                log.exception("project scanner")
            self._stop.wait(self.interval)
