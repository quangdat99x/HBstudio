"""Pipeline graph of one desk (doc | news) for the /<kind>/pipeline page.

The nodes are the desk's real workflow steps (workflow.FLOWS) plus a start node (defaults of new projects) and an end
node (YouTube upload). Live numbers come from project_steps (where every project stands) and messages (Claude turns:
running progress, average time and cost per step). Node settings are the same keys the Settings page edits.
"""
from __future__ import annotations

from . import config, db, workflow

MODELS = ["", "fable", "opus", "sonnet", "haiku"]
EFFORTS = ["", "low", "medium", "high", "xhigh", "max"]

# Extra settings shown on a step node besides its Claude model / effort.
STEP_FIELDS = {
    "cast": [("image_model_draft", "Model ảnh thử vai", "text")],
    "images": [("image_model", "Model ảnh chính", "text"), ("image_model_edit", "Model ảnh biến thể", "text"),
               ("image_model_draft", "Model ảnh nháp", "text"),
               ("gemini_web_mode", "Gemini web: cửa sổ trình duyệt", ["hidden", "headless", "show"]),
               ("gemini_web_fallback", "Gemini web lỗi / hết lượt thì dùng (trống = dừng)", "text"),
               ("gemini_web_delogo", "Gemini web: làm mờ logo góc ảnh", "bool")],
    "footage": [("tts_model", "Model giọng đọc", "text"), ("video_model", "Model video", "text")],
}


def _start_fields(kind: str) -> list[tuple]:
    f = [("auto_advance", "Tự chạy hết các bước (không chờ duyệt)", "bool"),
         ("budget_usd", "Ngân sách mỗi dự án (USD)", "number"), ("target_sec", "Thời lượng mặc định (giây)", "number"),
         ("format", "Khung hình", ["16:9", "9:16"]), ("language", "Ngôn ngữ", "text"),
         (f"model_desk_{kind}", "Model mặc định của mảng", MODELS), (f"effort_desk_{kind}", "Effort mặc định của mảng", EFFORTS)]
    if kind == "doc":
        f.insert(1, ("pipeline", "Cách dựng hình", list(config.PIPELINES)))
    if kind == "news":
        f.append(("news_enabled", "Theo dõi tin nền", "bool"))
    return f


def _fields(specs: list[tuple], settings: dict) -> list[dict]:
    return [{"key": k, "label": lbl, "kind": kd, "value": settings.get(k, config.DEFAULT_SETTINGS.get(k, ""))}
            for k, lbl, kd in specs]


def editable(kind: str) -> set[str]:
    keys = {k for k, *_ in _start_fields(kind)} | {f"yt_time_{kind}", "yt_visibility", "claude_parallel"}
    for step in workflow.flow(kind).keys:
        keys |= {f"model_{kind}_{step}", f"effort_{kind}_{step}"} | {k for k, *_ in STEP_FIELDS.get(step, [])}
    return (keys & set(config.DEFAULT_SETTINGS)) - set(config.SECRET_KEYS)


def _turn_stats(kind: str, step: str) -> dict:
    s = db.row("""SELECT SUM(m.status='done') AS done, SUM(m.status='failed') AS failed,
                         AVG(CASE WHEN m.status='done' THEN m.duration_sec END) AS avg_sec,
                         AVG(CASE WHEN m.status='done' THEN m.cost_usd END) AS avg_cost
                  FROM messages m JOIN projects p ON p.id=m.project_id
                  WHERE m.role='assistant' AND m.kind='step' AND m.step=? AND COALESCE(p.kind,'doc')=?""", (step, kind)) or {}
    active = db.rows("""SELECT m.project_id, m.status, m.progress_msg, m.started_at, p.title
                        FROM messages m JOIN projects p ON p.id=m.project_id
                        WHERE m.role='assistant' AND m.status IN ('queued','running') AND m.step=? AND COALESCE(p.kind,'doc')=?
                        ORDER BY m.id""", (step, kind))
    last_err = db.row("""SELECT m.project_id, p.title, m.error FROM messages m JOIN projects p ON p.id=m.project_id
                         WHERE m.role='assistant' AND m.kind='step' AND m.status='failed' AND m.step=? AND COALESCE(p.kind,'doc')=?
                         ORDER BY m.id DESC LIMIT 1""", (step, kind))
    return {"done": s.get("done") or 0, "failed_turns": s.get("failed") or 0,
            "avg_sec": round(s["avg_sec"]) if s.get("avg_sec") else None,
            "avg_cost": round(s["avg_cost"], 2) if s.get("avg_cost") else None,
            "running": sum(1 for a in active if a["status"] == "running"),
            "queued": sum(1 for a in active if a["status"] == "queued"), "active": active, "last_error": last_err}


def graph(kind: str) -> dict:
    fl = workflow.flow(kind)
    settings = db.all_settings()
    projects = db.rows("SELECT id, title, auto_advance FROM projects WHERE COALESCE(kind,'doc')=? AND archived=0 "
                       "ORDER BY updated_at DESC", (kind,))
    step_rows = db.rows("""SELECT s.project_id, s.step, s.status, s.error FROM project_steps s JOIN projects p ON p.id=s.project_id
                           WHERE COALESCE(p.kind,'doc')=? AND p.archived=0""", (kind,))
    by_proj: dict[int, dict] = {}
    for r in step_rows:
        by_proj.setdefault(r["project_id"], {})[r["step"]] = r
    # Where each project stands: the first step that is not approved (same rule as store.current_step).
    at: dict[str, list] = {k: [] for k in fl.keys}
    finished = []
    for p in projects:
        rows = by_proj.get(p["id"], {})
        cur = next((k for k in fl.keys if (rows.get(k) or {}).get("status", "locked") != "approved"), None)
        if cur is None:
            finished.append(p)
        else:
            r = rows.get(cur) or {}
            at[cur].append({**p, "status": r.get("status", "locked"), "error": r.get("error")})

    nodes = [{"id": "start", "label": "Dự án mới", "icon": "✨", "desc": "Mặc định cho dự án tạo mới của mảng này.",
              "kind": "start", "projects": [], "n_here": len(projects), "stats": None,
              "fields": _fields(_start_fields(kind), settings)}]
    for st in fl.steps:
        here = at[st.key]
        specs = [(f"model_{kind}_{st.key}", "Model Claude", MODELS), (f"effort_{kind}_{st.key}", "Effort", EFFORTS)]
        specs += STEP_FIELDS.get(st.key, []) if kind == "doc" or st.key != "cast" else []
        nodes.append({"id": st.key, "label": f"{st.num} · {st.name}", "icon": st.icon, "desc": st.goal, "kind": "step",
                      "gate": st.gate, "spends": st.spends, "projects": here, "n_here": len(here),
                      "counts": {s: sum(1 for x in here if x["status"] == s) for s in ("review", "failed", "ready", "locked")},
                      "stats": _turn_stats(kind, st.key), "fields": _fields(specs, settings)})
    nodes.append({"id": "publish", "label": "Đăng YouTube", "icon": "📤", "desc": "Dự án đã duyệt metadata: sẵn sàng đăng hoặc đã đăng.",
                  "kind": "end", "projects": finished[:40], "n_here": len(finished), "stats": None,
                  "fields": _fields([("yt_visibility", "Chế độ đăng", ["schedule", "private", "unlisted", "public"]),
                                     (f"yt_time_{kind}", "Giờ đăng mặc định", "text")], settings)})
    # Layout: one row, left to right (the page lets the user drag nodes and remembers it).
    for i, n in enumerate(nodes):
        n["x"], n["y"] = 40 + i * 230, 160
    edges = [{"from": a["id"], "to": b["id"]} for a, b in zip(nodes, nodes[1:])]
    return {"kind": kind, "label": config.KINDS[kind]["label"], "nodes": nodes, "edges": edges,
            "parallel": settings.get("claude_parallel")}


# Source files behind each step, handed to Claude in the dev chat (paths relative to the app folder).
COMMON_STEP_FILES = ["creater/workflow.py (Step của bước + _check_<bước>/_view_<bước>)", "creater/worker.py (chạy lượt Claude)",
                     "creater/prompts.py (prompt gửi Claude)", "templates/_step_panel.html"]
STEP_FILES = {
    "script": ["creater/blueprint.py", "creater/overview.py", "templates/blueprint.html"],
    "cast": ["creater/gen.py (lệnh image: ảnh thử vai)", "creater/providers.py"],
    "scenes": ["creater/overview.py"],
    "images": ["creater/gen.py (cmd_image)", "creater/providers.py", "creater/gemini_web.py (ảnh qua gemini.google.com)",
               "C:/Tool/bgremove (tách nền)"],
    "footage": ["creater/gen.py (cmd_tts, cmd_sfx, cmd_video)", "creater/media.py", "creater/providers.py"],
    "render": ["engine/ (Remotion: engine/src, engine/ENGINE.md)", "parallax/"],
    "metadata": ["creater/publish.py", "creater/yt_gpm.py"],
}
GRAPH_FILES = ("creater/pipeline_graph.py (STEP_FIELDS, STEP_FILES, graph), templates/pipeline.html, static/devchat.js, "
               "app.py (route /<kind>/pipeline); các bước thật của mảng: creater/workflow.py (DOC_STEPS, NEWS_STEPS)")


def dev_context(node: str) -> dict | None:
    """Node ids of the dev chat: "<kind>:<step>", "<kind>:start", "<kind>:publish", "<kind>:_all"."""
    kind, _, nid = node.partition(":")
    if kind not in config.KINDS:
        return None
    from . import store
    rules = f"{store.rules_path(kind)} (bộ quy tắc của mảng, mục 2.x hướng dẫn Claude làm từng bước; app tự lưu phiên bản khi file đổi)"
    fl = workflow.flow(kind)
    desk = config.KINDS[kind]["label"]
    base = {"graph_files": GRAPH_FILES,
            "extra": f"Mảng: {desk}. Bộ quy tắc: {rules}. Cài đặt mặc định: creater/config.py (DEFAULT_SETTINGS)."}
    if nid == "_all":
        return {**base, "label": f"Toàn bộ pipeline {desk}", "desc": "Cả luồng: " + " → ".join(s.name for s in fl.steps) + ".",
                "files": ["app.py", "creater/workflow.py", "creater/worker.py", "creater/store.py", "creater/schema.sql", "README.md"],
                "settings": []}
    if nid == "start":
        return {**base, "label": f"Dự án mới ({desk})", "desc": "Tạo dự án và mặc định của dự án mới.",
                "files": ["creater/store.py (create_project)", "creater/scaffold.py", "templates/projects.html"],
                "settings": [k for k, *_ in _start_fields(kind)]}
    if nid == "publish":
        return {**base, "label": f"Đăng YouTube ({desk})", "desc": "Đăng video qua GPM Login sau khi metadata được duyệt.",
                "files": ["creater/publish.py", "creater/yt_gpm.py", "templates/_upload.html", "templates/channels.html"],
                "settings": ["yt_visibility", f"yt_time_{kind}"]}
    st = fl.by_key.get(nid)
    if not st:
        return None
    return {**base, "label": f"{st.num} · {st.name} ({desk})", "desc": st.goal + f" Cổng duyệt: {st.gate}",
            "files": COMMON_STEP_FILES + STEP_FILES.get(nid, []) + ([f"Bộ quy tắc mục {st.rule}"] if st.rule else []),
            "settings": [f"model_{kind}_{nid}", f"effort_{kind}_{nid}"] + [k for k, *_ in STEP_FIELDS.get(nid, [])]}


def save_settings(kind: str, values: dict) -> dict:
    allowed = editable(kind)
    saved = {}
    for k, v in (values or {}).items():
        if k in allowed:
            db.set_setting(k, ("1" if v else "0") if isinstance(v, bool) else str(v).strip())
            saved[k] = db.get_setting(k)
    return {"saved": saved, "rejected": sorted(set(values or {}) - allowed)}
