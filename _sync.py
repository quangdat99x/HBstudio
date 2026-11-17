"""Đồng bộ code bộ tool giữa các máy qua Git (repo GitHub private, remote `origin`, nhánh `main`).

Tool Manager gọi:
  status(fetch)   máy này có gì chưa đẩy, máy kia có gì chưa kéo về
  sync()          commit thay đổi của máy này → kéo bản mới (rebase) → đẩy lên; trả về file/tool vừa đổi
  startup_pull()  lúc mở Tool Manager: kéo bản mới nếu máy này không có thay đổi dở dang

Chỉ code đi qua Git (.gitignore loại database, venv, model, log, output, file bí mật), nên mỗi máy giữ
dữ liệu và cài đặt riêng.

MÁY CHÍNH / MÁY PHỤ (_sync_main.json, có trên GitHub): chỉ máy chính được commit và đẩy code. Máy phụ:
  - Git của máy đó bị khoá đẩy (remote.origin.pushurl giả) và khoá commit (hook pre-commit), kể cả gõ tay;
  - nút Đồng bộ = "lấy code máy chính": file sửa trên máy phụ được sao lưu vào _sync_backup\\<thời gian>\\
    rồi bỏ, code về đúng bản GitHub. Không bao giờ có xung đột vì chỉ một máy viết.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRANCH = "main"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ROLE_FILE = os.path.join(BASE_DIR, "_sync_main.json")
NO_PUSH_URL = "KHONG-DUOC-DAY--chi-may-chinh-moi-day-code-len-GitHub"
_HOOK_TAG = "# _sync.py: may phu khong duoc commit"


def _git(*args, timeout=120):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C.UTF-8")
    try:
        p = subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_NO_WINDOW, env=env)
    except FileNotFoundError:
        return 127, "chưa cài Git (chạy _setup\\cai-git.bat)"
    except subprocess.TimeoutExpired:
        return 124, f"git {args[0]} quá {timeout} giây (mạng chậm hoặc đang chờ đăng nhập GitHub)"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def machine() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname()


def is_repo() -> bool:
    return os.path.isdir(os.path.join(BASE_DIR, ".git"))


# ---------------------------------------------------------------- máy chính / máy phụ
def main_machine() -> str:
    try:
        with open(ROLE_FILE, encoding="utf-8") as f:
            return str(json.load(f).get("main_machine") or "").strip()
    except (OSError, ValueError):
        return ""


def is_main() -> bool:
    """No _sync_main.json (old checkout) → every machine may push, as before."""
    main = main_machine()
    return not main or main.upper() == machine().upper()


def _hook_path() -> str:
    return os.path.join(BASE_DIR, ".git", "hooks", "pre-commit")


def enforce_role() -> None:
    """Lock pushing and committing in this machine's Git when it is not the main machine (unlock on the main one).
    Local Git config only, so it also stops a manual `git push` / `git commit` typed on the secondary machine."""
    if not is_repo():
        return
    code, cur = _git("config", "--get", "remote.origin.pushurl")
    hook = _hook_path()
    ours = False
    try:
        with open(hook, encoding="utf-8") as f:
            ours = _HOOK_TAG in f.read()
    except OSError:
        pass
    if is_main():
        if code == 0 and cur.strip() == NO_PUSH_URL:
            _git("config", "--unset", "remote.origin.pushurl")
        if ours:
            os.remove(hook)
        return
    if cur.strip() != NO_PUSH_URL:
        _git("config", "remote.origin.pushurl", NO_PUSH_URL)
    if not ours and not os.path.exists(hook):
        os.makedirs(os.path.dirname(hook), exist_ok=True)
        with open(hook, "w", encoding="utf-8", newline="\n") as f:
            f.write("#!/bin/sh\n" + _HOOK_TAG + "\n"
                    f"echo 'May nay la may phu: chi may chinh ({main_machine()}) duoc commit code.' >&2\n"
                    "echo 'Sua code tren may chinh roi bam Dong bo; may nay bam Dong bo de lay ban moi.' >&2\n"
                    "exit 1\n")


def remote_url() -> str:
    code, out = _git("remote", "get-url", "origin")
    return out if code == 0 else ""


def local_changes() -> list[str]:
    code, out = _git("status", "--porcelain", "-uall")
    if code != 0:
        return []
    files = []
    for ln in out.splitlines():
        if not ln.strip():
            continue
        f = ln[2:].strip().strip('"')   # not ln[3:]: _git() strips the output, so line 1 may have lost its leading space
        p = os.path.join(BASE_DIR, f)
        # a new file too big for Git is data: it never counts as a change (else startup_pull would never run)
        if ln.startswith("??") and os.path.isfile(p) and os.path.getsize(p) > MAX_FILE_MB * 1024 * 1024:
            continue
        files.append(f)
    return files


def _count(rng: str) -> int:
    code, out = _git("rev-list", "--count", rng)
    return int(out) if code == 0 and out.isdigit() else 0


def _head() -> str:
    code, out = _git("rev-parse", "HEAD")
    return out if code == 0 else ""


def status(fetch: bool = True) -> dict:
    if not is_repo():
        return {"ok": False, "error": "C:\\Tool chưa là repo Git"}
    enforce_role()
    url = remote_url()
    if not url:
        return {"ok": False, "error": "chưa nối GitHub (chưa có remote origin)", "changes": local_changes()}
    fetch_err = ""
    if fetch:
        code, out = _git("fetch", "-q", "origin", timeout=90)
        if code != 0:
            fetch_err = out.splitlines()[-1] if out else f"git fetch lỗi {code}"
    has_remote_branch = _git("rev-parse", "--verify", "-q", f"origin/{BRANCH}")[0] == 0
    ahead = _count(f"origin/{BRANCH}..HEAD") if has_remote_branch else _count("HEAD")
    behind = _count(f"HEAD..origin/{BRANCH}") if has_remote_branch else 0
    _, last = _git("log", "-1", "--format=%h %cd · %an · %s", "--date=format:%d/%m %H:%M")
    _, last_remote = _git("log", "-1", "--format=%cd · %an", "--date=format:%d/%m %H:%M", f"origin/{BRANCH}") \
        if has_remote_branch else (0, "")
    return {"ok": True, "machine": machine(), "main_machine": main_machine(), "is_main": is_main(),
            "remote": url, "changes": local_changes(), "ahead": ahead,
            "behind": behind, "last": last, "last_remote": last_remote, "fetch_error": fetch_err}


def _changed_between(old: str, new: str) -> list[str]:
    if not old or not new or old == new:
        return []
    code, out = _git("diff", "--name-only", old, new)
    return [ln.strip() for ln in out.splitlines() if ln.strip()] if code == 0 else []


MAX_FILE_MB = 50   # GitHub refuses files over 100 MB; anything this big is data, not code


def _unstage_big() -> list[str]:
    """Take files over MAX_FILE_MB back out of the commit (they stay on disk, untouched)."""
    code, out = _git("diff", "--cached", "--name-only", "--diff-filter=AM")
    big = []
    for f in (out.splitlines() if code == 0 else []):
        f = f.strip().strip('"')
        p = os.path.join(BASE_DIR, f)
        if f and os.path.isfile(p) and os.path.getsize(p) > MAX_FILE_MB * 1024 * 1024:
            big.append(f)
    for f in big:
        _git("reset", "-q", "--", f)
    return big


def _commit_local(changes: list[str]) -> tuple[bool, str, list[str]]:
    code, out = _git("add", "-A")
    if code != 0:
        return False, out, []
    big = _unstage_big()
    changes = [c for c in changes if c not in big]
    if _git("diff", "--cached", "--quiet")[0] == 0:   # nothing left to commit
        return True, "", big
    names = ", ".join(os.path.basename(c.rstrip("/")) for c in changes[:4]) + (f" +{len(changes) - 4} file" if len(changes) > 4 else "")
    msg = f"[{machine()}] {time.strftime('%d/%m/%Y %H:%M')}: {names}"
    code, out = _git("commit", "-q", "-m", msg)
    return code == 0, out, big


def _conflicts() -> list[str]:
    _, out = _git("diff", "--name-only", "--diff-filter=U")
    return [ln for ln in out.splitlines() if ln.strip()]


def sync() -> dict:
    """Main machine: commit → pull --rebase → push. Secondary machine: follow_main().
    Returns {ok, message, pulled: [files], pushed: n} or {ok: False, error}."""
    st = status(fetch=False)
    if not st.get("ok"):
        return st
    if not st["is_main"]:
        return follow_main()
    committed = 0
    skipped_big: list[str] = []
    if st["changes"]:
        ok, out, skipped_big = _commit_local(st["changes"])
        if not ok:
            return {"ok": False, "error": f"không commit được thay đổi của máy này: {out[-400:]}"}
        committed = len([c for c in st["changes"] if c not in skipped_big])
    code, out = _git("fetch", "origin", timeout=120)
    if code != 0:
        return {"ok": False, "error": "không kết nối được GitHub: " + (out.splitlines()[-1] if out else str(code)),
                "committed": committed}
    old = _head()
    pulled = []
    if _git("rev-parse", "--verify", "-q", f"origin/{BRANCH}")[0] == 0 and _count(f"HEAD..origin/{BRANCH}"):
        code, out = _git("rebase", f"origin/{BRANCH}", timeout=180)
        if code != 0:
            files = _conflicts()
            _git("rebase", "--abort")
            return {"ok": False, "conflict": files,
                    "error": "máy kia và máy này cùng sửa một chỗ, chưa gộp được: " + (", ".join(files) or out[-300:]) +
                             ". Code máy này vẫn nguyên (đã commit). Nhờ Claude gộp giúp rồi bấm Đồng bộ lại."}
        # files that came from the other machine = what changed between origin before and after, minus our own
        pulled = _changed_between(old, _head())
    ahead = _count(f"origin/{BRANCH}..HEAD") if _git("rev-parse", "--verify", "-q", f"origin/{BRANCH}")[0] == 0 \
        else _count("HEAD")
    pushed = 0
    if ahead:
        code, out = _git("push", "-u", "origin", BRANCH, timeout=300)
        if code != 0:
            return {"ok": False, "error": "đẩy lên GitHub lỗi: " + out[-400:], "pulled": pulled, "committed": committed}
        pushed = ahead
    reqs = _install_requirements(pulled)
    parts = []
    if committed:
        parts.append(f"đã commit {committed} file sửa trên máy này")
    if pulled:
        parts.append(f"đã kéo về {len(pulled)} file từ máy khác")
    if pushed:
        parts.append(f"đã đẩy {pushed} commit lên GitHub")
    if skipped_big:
        parts.append(f"bỏ qua {len(skipped_big)} file trên {MAX_FILE_MB} MB (dữ liệu, không đẩy lên): "
                     + ", ".join(os.path.basename(f) for f in skipped_big[:3]))
    return {"ok": True, "message": "; ".join(parts) or "đã đồng bộ, không có gì mới", "pulled": pulled,
            "pushed": pushed, "committed": committed, "requirements": reqs, "skipped_big": skipped_big}


def _backup(files: list[str], move_untracked: set[str]) -> str:
    """Copy this machine's version of `files` to _sync_backup\\<time>\\ (untracked ones are moved there)."""
    dest = os.path.join(BASE_DIR, "_sync_backup", time.strftime("%Y%m%d-%H%M%S") + "-may-phu")
    for f in files:
        src = os.path.join(BASE_DIR, f)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(dest, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if f in move_untracked:
            shutil.move(src, dst)
        else:
            shutil.copy2(src, dst)
    return dest if os.path.isdir(dest) else ""


def follow_main() -> dict:
    """Secondary machine: make the code exactly the main machine's version on GitHub.
    Whatever was edited or committed here is backed up first, then dropped."""
    code, out = _git("fetch", "origin", timeout=120)
    if code != 0:
        return {"ok": False, "error": "không kết nối được GitHub: " + (out.splitlines()[-1] if out else str(code))}
    if _git("rev-parse", "--verify", "-q", f"origin/{BRANCH}")[0] != 0:
        return {"ok": False, "error": "GitHub chưa có nhánh main (máy chính chưa đẩy code lần nào)"}
    _git("rebase", "--abort")   # a rebase left half-done by the old sync would block the reset
    _, untracked_out = _git("ls-files", "--others", "--exclude-standard")
    untracked = {ln.strip() for ln in untracked_out.splitlines() if ln.strip()}
    changes = local_changes()
    _, committed_out = _git("diff", "--name-only", f"origin/{BRANCH}...HEAD")   # files of local commits not on GitHub
    files = sorted(set(changes) | {ln.strip() for ln in committed_out.splitlines() if ln.strip()})
    backup = _backup(files, {f for f in files if f in untracked}) if files else ""
    old = _head()
    code, out = _git("reset", "--hard", "-q", f"origin/{BRANCH}")
    if code != 0:
        return {"ok": False, "error": "không lấy được code máy chính: " + out[-400:], "backup": backup}
    pulled = _changed_between(old, _head())
    parts = []
    if pulled:
        parts.append(f"đã lấy {len(pulled)} file mới từ máy chính ({main_machine()})")
    if files:
        parts.append(f"bỏ {len(files)} file sửa trên máy phụ (đã sao lưu vào {os.path.relpath(backup, BASE_DIR)})"
                     if backup else f"bỏ {len(files)} thay đổi trên máy phụ")
    return {"ok": True, "message": "; ".join(parts) or "code đã khớp máy chính", "pulled": pulled, "pushed": 0,
            "committed": 0, "discarded": files, "backup": backup, "requirements": _install_requirements(pulled)}


def startup_pull() -> dict:
    """At Tool Manager start: fast-forward to the newest code when this machine has nothing pending."""
    st = status(fetch=True)
    if not st.get("ok") or st.get("fetch_error") or st["changes"] or st["ahead"] or not st["behind"]:
        return {"ok": True, "pulled": [], "status": st}
    old = _head()
    code, out = _git("merge", "--ff-only", "-q", f"origin/{BRANCH}")
    if code != 0:
        return {"ok": False, "error": out[-300:], "status": st}
    pulled = _changed_between(old, _head())
    return {"ok": True, "pulled": pulled, "requirements": _install_requirements(pulled), "status": status(fetch=False)}


# ---------------------------------------------------------------- after a pull
def tool_dirs_changed(files: list[str]) -> set[str]:
    return {f.split("/", 1)[0] for f in files if "/" in f}


def _python_for(tool_dir: str) -> str:
    venv = os.path.join(tool_dir, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv):
        return venv
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return exe


def _install_requirements(files: list[str]) -> list[dict]:
    """A requirements.txt that came from the other machine is installed into that tool's interpreter."""
    out = []
    for f in files:
        if os.path.basename(f).lower() != "requirements.txt":
            continue
        tool_dir = os.path.join(BASE_DIR, os.path.dirname(f))
        if not os.path.exists(os.path.join(BASE_DIR, f)):
            continue
        py = _python_for(tool_dir)
        try:
            p = subprocess.run([py, "-m", "pip", "install", "-q", "-r", os.path.join(BASE_DIR, f)], cwd=tool_dir,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
                               creationflags=_NO_WINDOW)
            out.append({"file": f, "ok": p.returncode == 0, "log": ((p.stdout or "") + (p.stderr or ""))[-500:]})
        except Exception as e:  # noqa: BLE001
            out.append({"file": f, "ok": False, "log": str(e)})
    return out
