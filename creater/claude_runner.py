"""Run Claude Code headless (`claude -p`) and capture everything it says.

The prompt goes in through stdin (no command-line quoting issues, 10 MB cap is far away) and stream-json output
lets us keep every assistant message, not only the final line. Copied from JRE Studio (studio/pipeline/claude_runner.py).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import config, db

log = logging.getLogger("creater.claude")


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


def _safe_call(fn, *args) -> None:
    """Progress callbacks must never break a run."""
    if fn:
        try:
            fn(*args)
        except Exception:  # noqa: BLE001
            log.debug("progress callback failed", exc_info=True)
MODEL_ALIASES = ("fable", "opus", "sonnet", "haiku")


def run(prompt: str, *, cwd: Path | None = None, allowed_tools: str | None = None, permission_mode: str | None = None,
        max_turns: int | None = None, model: str | None = None, effort: str | None = None,
        fallback_model: str | None = None, timeout: int = 3 * 3600, log_path: Path | None = None, on_text=None,
        stop_flag=None, on_event=None, add_dirs: list[str] | None = None, tools: str | None = None,
        isolated: bool = False, resume: str | None = None, extra_args: list[str] | None = None,
        env_extra: dict | None = None) -> dict:
    """Execute one headless run.

    `tools` limits the built-in tool set the model sees (`--tools`); `allowed_tools` only pre-approves tools.
    `isolated` leaves out everything of the user's own setup that a pipeline step does not use and that would
    otherwise ride along in every request: MCP servers and claude.ai connectors (hundreds of tool names), the
    skill and slash-command list, auto-memory. The caller then passes the skill text inside the prompt.
    `resume` continues an earlier session (same context, prompt cache still warm) instead of starting over.
    `extra_args` / `env_extra` add CLI flags and environment variables (the documentary runs keep the claude.ai
    connectors for Higgsfield but drop the slash-command list and auto-memory this way).

    Returns {ok, error, text, texts, result, usage, models, model_usage, cost_usd, duration_sec, returncode,
    session_id, log_path}. `models` lists the model ids the CLI actually used (from the result event), so the
    caller can show which model answered even when the setting is empty (= Claude Code's default for the account).
    """
    cmd = _command()
    if not cmd:
        return {"ok": False, "error": "Claude Code CLI chưa cài (xem README: E:\\Tool\\claude-cli)", "text": ""}
    cwd = Path(cwd or config.BASE_DIR)
    args = cmd + ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                  "--permission-mode", permission_mode or db.get_setting("claude_permission_mode")]
    if resume:
        args += ["--resume", resume]
    if isolated:
        args += ["--strict-mcp-config", "--disable-slash-commands"]
    args += list(extra_args or [])
    for d in add_dirs or []:
        if d and Path(d).exists():
            args += ["--add-dir", str(d)]              # variadic flag: always followed by another flag below
    args += ["--max-turns", str(max_turns or db.setting_int("claude_max_turns"))]
    if tools is not None:
        args += ["--tools", tools]                     # variadic too; "" = no tools at all
    allowed = allowed_tools or db.get_setting("claude_allowed_tools")
    if allowed:
        args += ["--allowedTools", allowed]
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
    if isolated:
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"   # memory indexes are for chat sessions
        env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"   # claude.ai connectors (Canva, ElevenLabs, Trello, ...)
    env.update({k: str(v) for k, v in (env_extra or {}).items()})
    started = time.time()
    log.info("claude run in %s: %s", cwd, " ".join(args[len(cmd):]))
    logf = open(log_path, "w", encoding="utf-8") if log_path else None
    texts, result, usage, cost, is_error, err_msg = [], "", {}, None, False, ""
    model_usage: dict = {}
    session_id = resume or ""
    written = {"text": 0, "tool": 0}      # characters streamed so far (answer text / tool input such as a file body)
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
        partial = line.startswith('{"type":"stream_event"')
        if logf and not partial:                 # partial chunks would bloat the log; final messages are kept
            logf.write(line)
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        et = ev.get("type")
        if ev.get("session_id"):
            session_id = ev["session_id"]
        if et == "stream_event":
            delta = (ev.get("event") or {}).get("delta") or {}
            if delta.get("type") == "text_delta":
                written["text"] += len(delta.get("text") or "")
                _safe_call(on_event, "text_delta", delta.get("text") or "")
                _safe_call(on_event, "writing", written["text"])
            elif delta.get("type") == "input_json_delta":
                written["tool"] += len(delta.get("partial_json") or "")
                _safe_call(on_event, "writing_tool", written["tool"])
            continue
        if et == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text"):
                    texts.append(block["text"])
                    if on_text:
                        on_text(block["text"])
                    _safe_call(on_event, "text", block["text"])
                elif block.get("type") == "tool_use":
                    _safe_call(on_event, "tool", (block.get("name") or "", block.get("input") or {}))
        elif et == "system" and ev.get("subtype") == "thinking_tokens":
            _safe_call(on_event, "thinking", int(ev.get("estimated_tokens_delta") or 0))
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
    return {"ok": ok, "error": None if ok else err_msg, "text": text, "texts": texts, "result": result, "usage": usage,
            "models": list(model_usage.keys()), "model_usage": model_usage,
            "cost_usd": cost, "duration_sec": round(time.time() - started, 1), "returncode": proc.returncode,
            "session_id": session_id or None, "log_path": str(log_path) if log_path else None}


_USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")


def merge_runs(runs: list[dict]) -> dict:
    """Totals of several runs of one job (a first run plus the resumed fix-ups) for describe_run.

    `usage` of a resumed run covers that invocation only, but its `total_cost_usd` is the running total of the
    whole session, so cost is taken from the last run of each session.
    """
    runs = [r for r in runs if r]
    if not runs:
        return {}
    usage = {k: sum((r.get("usage") or {}).get(k) or 0 for r in runs) for k in _USAGE_KEYS}
    usage["output_tokens_details"] = {"thinking_tokens": sum(
        ((r.get("usage") or {}).get("output_tokens_details") or {}).get("thinking_tokens") or 0 for r in runs)}
    models, cost_by_session = [], {}
    for i, r in enumerate(runs):
        models += [m for m in r.get("models") or [] if m not in models]
        if r.get("cost_usd") is not None:
            cost_by_session[r.get("session_id") or f"run{i}"] = r["cost_usd"]
    return {**runs[-1], "usage": usage, "models": models, "cost_usd": sum(cost_by_session.values()) or None,
            "duration_sec": round(sum(r.get("duration_sec") or 0 for r in runs), 1)}


def _tok(n: float) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1000:.0f}k"


def describe_run(res: dict) -> str:
    """One-line summary for job messages: model · tokens (how much of it is cheap cache re-reads) · cost · time."""
    if not res:
        return ""
    models = ",".join(res.get("models") or []) or "model mặc định"
    u = res.get("usage") or {}
    cached = u.get("cache_read_input_tokens") or 0
    out = u.get("output_tokens") or 0
    tokens = sum(u.get(k) or 0 for k in _USAGE_KEYS)
    parts = [models]
    if tokens:
        parts.append(f"{_tok(tokens)} token" + (f" ({_tok(cached)} đọc lại cache)" if cached else ""))
    if out:
        thinking = (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
        parts.append(f"viết {_tok(out)}" + (f" ({_tok(thinking)} suy nghĩ)" if thinking else ""))
    if res.get("cost_usd"):
        parts.append(f"${res['cost_usd']:.2f}")
    if res.get("duration_sec"):
        parts.append(f"{res['duration_sec'] / 60:.0f} phút" if res["duration_sec"] >= 120 else f"{res['duration_sec']:.0f}s")
    return " · ".join(parts)


def probe(model: str | None = None, effort: str | None = None) -> dict:
    """One tiny turn to show login state and which model actually answers with the given settings."""
    res = run("Reply with exactly: OK", cwd=config.BASE_DIR, permission_mode="dontAsk", max_turns=1, timeout=180,
              model=model, effort=effort, fallback_model="")
    text = (res.get("result") or res.get("error") or "").strip()
    res["logged_in"] = res.get("ok") or ("Not logged in" not in text and "login" not in text.lower())
    res["summary"] = describe_run(res)
    return res
