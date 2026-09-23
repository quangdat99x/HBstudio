"""Run Claude Code headless (`claude -p`) and capture everything it says.

The prompt goes in through stdin (no command-line quoting issues, 10 MB cap is far away), skills are
discovered from E:\\DataBase\\.claude\\skills because cwd is the project folder, and stream-json output
lets us keep every assistant message, not only the final line.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from .. import config, db
from ..textfmt import md_to_html

log = logging.getLogger("studio.claude")


def _command() -> list[str] | None:
    """Prefer `node cli.js` (npm global install) so no .cmd shim is involved; fall back to the configured command."""
    cli = db.get_setting("claude_cli") or "claude"
    if cli != "claude" and Path(cli).exists():
        return [cli]
    # Preferred: the copy installed under E:\Tool\claude-cli. The Claude desktop app is an MSIX package,
    # so anything installed into %APPDATA% from inside it is virtualized and invisible to other processes.
    local_exe = config.CLAUDE_CLI_DIR / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if local_exe.exists():
        return [str(local_exe)]
    appdata = os.environ.get("APPDATA", "")
    pkg = Path(appdata) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code"
    exe = pkg / "bin" / "claude.exe"          # npm package ships a native binary (what claude.cmd runs)
    if exe.exists():
        return [str(exe)]
    cli_js = pkg / "cli.js"
    node = shutil.which("node")
    if cli_js.exists() and node:
        return [node, str(cli_js)]
    found = shutil.which("claude.exe") or shutil.which(cli)
    if found:
        if found.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", found]
        return [found]
    return None


def cli_status() -> dict:
    cmd = _command()
    base = {"token": _has_token(), "logged_in": _logged_in()}
    if not cmd:
        return {"installed": False, "version": "", **base}
    try:
        out = subprocess.run(cmd + ["--version"], capture_output=True, text=True, timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"installed": out.returncode == 0, "version": (out.stdout or out.stderr).strip()[:120],
                "command": " ".join(cmd), **base}
    except Exception as e:  # noqa: BLE001
        return {"installed": False, "version": str(e), **base}


def _has_token() -> bool:
    return bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))


def _logged_in() -> bool:
    """`/login` stores OAuth credentials in ~/.claude/.credentials.json on Windows."""
    return (Path.home() / ".claude" / ".credentials.json").exists()


EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
MODEL_ALIASES = ("fable", "opus", "sonnet", "haiku")


def run(prompt: str, *, cwd: Path | None = None, allowed_tools: str | None = None, permission_mode: str | None = None,
        max_turns: int | None = None, model: str | None = None, effort: str | None = None,
        fallback_model: str | None = None, timeout: int = 3 * 3600, log_path: Path | None = None, on_text=None,
        stop_flag=None) -> dict:
    """Execute one headless run.

    Returns {ok, error, text, result, usage, models, model_usage, cost_usd, duration_sec, returncode, log_path}.
    `models` lists the model ids the CLI actually used (from the result event), so the caller can show which
    model answered even when the setting is empty (= Claude Code's default for the account).
    """
    cmd = _command()
    if not cmd:
        return {"ok": False, "error": "Claude Code CLI chưa cài (xem README: E:\\Tool\\claude-cli)", "text": ""}
    cwd = Path(cwd or config.BASE_DIR)
    args = cmd + ["-p", "--output-format", "stream-json", "--verbose",
                  "--permission-mode", permission_mode or db.get_setting("claude_permission_mode"),
                  "--max-turns", str(max_turns or db.setting_int("claude_max_turns"))]
    tools = allowed_tools or db.get_setting("claude_allowed_tools")
    if tools:
        args += ["--allowedTools", tools]
    model = (model or db.get_setting("claude_model") or "").strip()
    if model:
        args += ["--model", model]
    effort = (effort or "").strip().lower()
    if effort in EFFORT_LEVELS:
        args += ["--effort", effort]
    fallback_model = (fallback_model if fallback_model is not None else db.get_setting("claude_fallback_model") or "").strip()
    if fallback_model:
        args += ["--fallback-model", fallback_model]
    env = dict(os.environ, PYTHONUTF8="1", CLAUDECODE="")
    env.pop("CLAUDECODE", None)      # never look like a nested Claude Code session
    started = time.time()
    log.info("claude run in %s: %s", cwd, " ".join(args[len(cmd):]))
    logf = open(log_path, "w", encoding="utf-8") if log_path else None
    texts, result, usage, cost, is_error, err_msg = [], "", {}, None, False, ""
    model_usage: dict = {}
    try:
        proc = subprocess.Popen(args, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace", env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        return {"ok": False, "error": f"không chạy được Claude CLI: {e}", "text": ""}
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except OSError:
        pass
    deadline = started + timeout
    for line in proc.stdout:
        if stop_flag and stop_flag():
            proc.kill()
            err_msg = "dừng theo yêu cầu"
            is_error = True
            break
        if logf:
            logf.write(line)
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        et = ev.get("type")
        if et == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text"):
                    texts.append(block["text"])
                    if on_text:
                        on_text(block["text"])
        elif et == "result":
            result = ev.get("result") or ""
            usage = ev.get("usage") or {}
            cost = ev.get("total_cost_usd")
            model_usage = ev.get("modelUsage") or {}
            is_error = bool(ev.get("is_error"))
            if is_error:
                err_msg = result or ev.get("error") or "run ended with is_error"
        if time.time() > deadline:
            proc.kill()
            err_msg = f"timeout sau {timeout}s"
            is_error = True
            break
    stderr = proc.stderr.read() if proc.stderr else ""
    proc.wait()
    if logf:
        if stderr:
            logf.write("\n--- stderr ---\n" + stderr)
        logf.close()
    if proc.returncode != 0 and not err_msg:
        err_msg = (stderr or result or f"exit code {proc.returncode}")[:800]
    text = "\n\n".join(texts)
    if result and result not in text:
        text = (text + "\n\n" + result).strip()
    ok = proc.returncode == 0 and not is_error
    return {"ok": ok, "error": None if ok else err_msg, "text": text, "result": result, "usage": usage,
            "models": list(model_usage.keys()), "model_usage": model_usage,
            "cost_usd": cost, "duration_sec": round(time.time() - started, 1), "returncode": proc.returncode,
            "log_path": str(log_path) if log_path else None}


def describe_run(res: dict) -> str:
    """One-line summary for job messages: model · tokens · cost."""
    if not res:
        return ""
    models = ",".join(res.get("models") or []) or "model mặc định"
    u = res.get("usage") or {}
    tokens = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + \
             (u.get("cache_creation_input_tokens") or 0) + (u.get("output_tokens") or 0)
    parts = [models]
    if tokens:
        parts.append(f"{tokens/1000:.0f}k token")
    if res.get("cost_usd"):
        parts.append(f"${res['cost_usd']:.2f}")
    if res.get("duration_sec"):
        parts.append(f"{res['duration_sec']:.0f}s")
    return " · ".join(parts)


def ask(question: str) -> dict:
    """Answer a natural-language question about the highlight database through the /kho-highlight skill."""
    config.WORK_DIR.mkdir(exist_ok=True)
    log_path = config.WORK_DIR / f"ask_{int(time.time())}.jsonl"
    prompt = f"/kho-highlight {question}"
    res = run(prompt, cwd=config.BASE_DIR, allowed_tools="Bash,Read,Glob,Grep,Write", permission_mode="acceptEdits",
              max_turns=40, timeout=1800, log_path=log_path,
              model=db.get_setting("claude_model_ask") or None, effort=db.get_setting("claude_effort_ask") or None)
    res["html"] = md_to_html(res.get("text") or "")
    res["summary"] = describe_run(res)
    return res


def probe(model: str | None = None, effort: str | None = None) -> dict:
    """One tiny turn to show login state and which model actually answers with the given settings."""
    res = run("Reply with exactly: OK", cwd=config.BASE_DIR, permission_mode="dontAsk", max_turns=1, timeout=180,
              model=model, effort=effort, fallback_model="")
    text = (res.get("result") or res.get("error") or "").strip()
    res["logged_in"] = res.get("ok") or ("Not logged in" not in text and "login" not in text.lower())
    res["summary"] = describe_run(res)
    return res
