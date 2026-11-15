"""gen.py: the command a headless turn runs to make a film's assets with the APIs set on the Settings page.

    "$CREATER_PYTHON" "$GEN_PY" <command> --help

  check                          keys, ElevenLabs plan and characters left, fal balance
  voices  [--lang ru] [--q ..]   ElevenLabs voice library (or --mine); --add VOICE --owner OWNER adds one to the account
  tts     --text-file f --out x.mp3 [--voice ID] [--model eleven_v4] [--takes 2] [--timestamps]   narration
  sfx     --prompt ".." --seconds 3 --out x.mp3                     sound effect (ElevenLabs)
  image   --prompt ".." --out x.png [--model main|draft|edit|<fal id>|openai:<model>|google:<model>] [--ref a.png]
          [--aspect 16:9] [--n 2]     (openai:/google: = straight to OpenAI / Google with their own key;
          gemini-web:<mode> = gemini.google.com with the user's Gemini plan, $0, one picture at a time, ~1 min each:
          run these one after another, never in parallel)
  gemini-web login|status        Chrome profile of gemini-web (login opens a window to sign in)
  video   --image start.png --prompt ".." --out x.mp4 [--seconds 5] [--end end.png] [--audio]
  run     <fal endpoint> --set k=v --file k=path --out x          any other fal model
  schema  <fal endpoint>         parameters of a fal model · models --q ".."  search the fal catalog
  price   <fal endpoint>         unit price · cost  what the project has spent against its budget

Paths are relative to the current folder. Every paid call is written to <project>/notes/costs.json (USD) and refused
when it would take the project past project.json budget_usd, unless --over-budget is given (only after the user
agreed). The keys stay in the app's settings: they never appear in commands or output.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import config, db, providers as pv
from .providers import ApiError

# ---------------------------------------------------------------- project ledger (notes/costs.json)


def find_project(start: Path) -> Path | None:
    for d in (start, *start.parents):
        if (d / "project.json").is_file():
            return d
    return None


class Ledger:
    def __init__(self, project: Path | None):
        self.project = project
        self.path = project / "notes" / "costs.json" if project else None
        try:
            self.info = json.loads((project / "project.json").read_text(encoding="utf-8")) if project else {}
        except (OSError, ValueError):
            self.info = {}

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def spent(self) -> float:
        return round(float(self._read().get("total_usd") or 0), 4)

    def budget(self) -> float | None:
        b = self.info.get("budget_usd")
        return float(b) if isinstance(b, (int, float)) else None

    def step(self) -> str:
        steps = self.info.get("steps") or {}
        return next((k for k, v in steps.items() if v == "running"), "chat")

    def guard(self, est: float | None, over: bool) -> None:
        budget = self.budget()
        if budget is None or over:
            return
        spent = self.spent()
        if spent + (est or 0) > budget + 1e-9:
            fail(f"VƯỢT NGÂN SÁCH: dự án đã tiêu ${spent:.2f}, lần này ước tính ${est or 0:.2f}, ngân sách ${budget:.2f}. "
                 "Dừng và hỏi người dùng; nếu họ đồng ý thì chạy lại với --over-budget (hoặc họ nâng ngân sách ở Thông tin dự án).",
                 code=3)

    def add(self, event: dict) -> None:
        if not self.path:
            return
        lock = self.path.with_suffix(".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(100):                            # several gen.py may run at once
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                if time.time() - lock.stat().st_mtime > 60:
                    lock.unlink(missing_ok=True)
                time.sleep(0.1)
        try:
            data = self._read()
            events = data.get("events") if isinstance(data.get("events"), list) else []
            events.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "step": self.step(), **event})
            total = round(sum(float(e.get("usd") or 0) for e in events), 4)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"total_usd": total, "budget_usd": self.budget(), "events": events},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        finally:
            lock.unlink(missing_ok=True)


# ---------------------------------------------------------------- output helpers
def say(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1):
    print(f"LỖI: {msg}", flush=True)
    raise SystemExit(code)


def result(data: dict) -> None:
    print("RESULT " + json.dumps(data, ensure_ascii=False, default=str), flush=True)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _short(payload: dict) -> dict:
    """Request as printed: data URIs cut short."""
    def cut(v):
        if isinstance(v, str) and v.startswith("data:"):
            return v[:40] + f"…({len(v) // 1024} KB)"
        if isinstance(v, list):
            return [cut(x) for x in v]
        return v
    return {k: cut(v) for k, v in payload.items()}


def _tools(name: str) -> str | None:
    env = {"ffmpeg": "FFMPEG", "ffprobe": "FFPROBE"}[name]
    exe = os.environ.get(env) or shutil.which(name)
    if not exe:
        fallback = config.FFMPEG_FALLBACK if name == "ffmpeg" else config.FFPROBE_FALLBACK
        exe = str(fallback) if fallback.exists() else None
    return exe


def duration_of(path: Path) -> float | None:
    probe = _tools("ffprobe")
    if not probe:
        return None
    try:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------- check, voices
def cmd_check(args) -> None:
    out = {}
    if pv.has_key("elevenlabs_api_key"):
        r = pv.el_check()
        out["elevenlabs"] = r
        say("ElevenLabs: " + (f"✓ gói {r.get('tier')} · đã dùng {r.get('used'):,}/{r.get('limit'):,} ký tự · còn {r.get('left'):,}"
                              + (f" · làm mới {r.get('reset')}" if r.get("reset") else "") if r["ok"] else f"✕ {r['error']}"))
    else:
        say("ElevenLabs: chưa có key (Cài đặt → API tạo nguyên liệu)")
    if pv.has_key("fal_api_key"):
        r = pv.fal_check()
        out["fal"] = r
        bal = f" · số dư ${r['balance']}" if r.get("balance") is not None else (f" · {r['balance_note']}" if r.get("balance_note") else "")
        say("fal.ai: " + (f"✓ key hợp lệ{bal}" if r["ok"] else f"✕ {r['error']}"))
    else:
        say("fal.ai: chưa có key (Cài đặt → API tạo nguyên liệu)")
    for name, label, fn in (("openai", "OpenAI (ảnh GPT trực tiếp)", pv.openai_check), ("google", "Google Gemini (ảnh trực tiếp)", pv.google_check)):
        if pv.has_key(f"{name}_api_key"):
            r = fn()
            out[name] = r
            say(f"{label}: " + ((f"✓ key hợp lệ · model ảnh: {', '.join(r['models'][:8])}" if r.get("models") else f"! {r.get('note')}")
                                if r["ok"] else f"✕ {r['error']}"))
        else:
            say(f"{label}: chưa có key (tùy chọn)")
    say("Model: tts " + pv.tts_model()[0] + " · ảnh " + pv.endpoint("main") + " · ảnh rẻ " + pv.endpoint("draft")
        + " · sửa ảnh " + pv.endpoint("edit") + " · video " + pv.endpoint("video"))
    say("Giọng theo ngôn ngữ: " + ", ".join(f"{k}={v.get('name')} ({v.get('id')})" for k, v in pv.voices_map().items()))
    result(out)


def cmd_voices(args) -> None:
    if args.add:
        if not args.owner:
            fail("--add cần --owner (public_owner_id, lấy từ danh sách voices)")
        r = pv.el_add_voice(args.owner, args.add, args.name or args.add)
        say(f"✓ đã thêm giọng vào tài khoản: {r.get('voice_id') or args.add}")
        result(r)
        return
    voices = pv.el_my_voices() if args.mine else pv.el_library_voices(args.lang, args.q, args.gender, args.limit)
    for v in voices:
        tags = " · ".join(x for x in (v.get("gender"), v.get("age"), v.get("accent"), v.get("language"), v.get("use_case")) if x)
        say(f"{v['id']} | {v['name']} | {tags}" + (f" | owner {v['owner']}" if v.get("owner") else "")
            + (f"\n    {v['description'][:160]}" if v.get("description") else ""))
    say(f"({len(voices)} giọng)")


# ---------------------------------------------------------------- ElevenLabs: narration, sound effects
def _speak(text: str, voice: dict, out: Path, model: str, lang: str | None, vs: dict, seed: int | None,
           timestamps: bool) -> dict:
    """One take, split under the model's per-request limit and joined back when the text is long."""
    limit = pv.tts_model(model)[1][2] - 200
    pieces = pv._split_text(text, limit)
    if len(pieces) == 1:
        return pv.el_tts(text, voice["id"], out, model_id=model, language=lang, voice_settings=vs, seed=seed,
                         timestamps=timestamps)
    ffmpeg = _tools("ffmpeg")
    if not ffmpeg:
        fail("văn bản dài cần ffmpeg để nối các đoạn")
    parts, chars, merged, offset = [], 0, {"characters": [], "character_start_times_seconds": [],
                                           "character_end_times_seconds": []}, 0.0
    for i, piece in enumerate(pieces):
        part = out.with_name(f"{out.stem}.part{i + 1}{out.suffix}")
        r = pv.el_tts(piece, voice["id"], part, model_id=model, language=lang, voice_settings=vs, seed=seed,
                      timestamps=timestamps, previous_text=pieces[i - 1] if i else None,
                      next_text=pieces[i + 1] if i + 1 < len(pieces) else None)
        chars += r["chars"]
        parts.append(part)
        if timestamps and r.get("alignment"):
            a = r["alignment"]
            merged["characters"] += list(a.get("characters") or []) + ["\n"]
            merged["character_start_times_seconds"] += [offset + t for t in a.get("character_start_times_seconds") or []] + [offset]
            merged["character_end_times_seconds"] += [offset + t for t in a.get("character_end_times_seconds") or []] + [offset]
        offset += duration_of(part) or (r["alignment"]["character_end_times_seconds"][-1] if r.get("alignment") else 0)
        say(f"  đoạn {i + 1}/{len(pieces)}: {len(piece)} ký tự")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", "concat:" + "|".join(str(p) for p in parts), "-c", "copy", str(out)],
                   check=True)
    for p in parts:
        p.unlink(missing_ok=True)
    return {"file": out, "chars": chars, "request_id": None, "alignment": merged if timestamps else None, "model": model}


def _words(alignment: dict) -> list[dict]:
    words, cur, start, end = [], "", None, None
    for ch, s, e in zip(alignment.get("characters") or [], alignment.get("character_start_times_seconds") or [],
                        alignment.get("character_end_times_seconds") or []):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": round(start, 3), "end": round(end, 3)})
            cur, start = "", None
            continue
        cur += ch
        start = s if start is None else start
        end = e
    if cur:
        words.append({"word": cur, "start": round(start, 3), "end": round(end, 3)})
    return words


def cmd_tts(args, ledger: Ledger) -> None:
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else (args.text or "")
    text = text.strip()
    if not text:
        fail("chưa có lời đọc (--text hoặc --text-file)")
    lang = args.lang or ledger.info.get("language")
    voice = {"id": args.voice} if args.voice else pv.voice_for(lang)
    if not voice.get("id"):
        fail(f"chưa chọn giọng cho ngôn ngữ {lang or 'en'} (Cài đặt → Giọng theo ngôn ngữ, hoặc --voice ID)")
    model, meta = pv.tts_model(args.model)
    vs = {"stability": args.stability, "similarity_boost": args.similarity, "style": args.style, "speed": args.speed}
    takes = max(1, min(5, args.takes))
    est = pv.tts_usd(len(text), model) * takes
    ledger.guard(est, args.over_budget)
    out = Path(args.out)
    say(f"Đọc {len(text):,} ký tự × {takes} bản · {meta[0]} · giọng {voice.get('name') or voice['id']} · ước tính ${est:.3f}")
    files = []
    for i in range(takes):
        target = out if takes == 1 else out.with_name(f"{out.stem}{i + 1}{out.suffix}")
        seed = (args.seed + i) if args.seed is not None else None
        try:
            r = _speak(text, voice, target, model, lang, vs, seed, args.timestamps)
        except ApiError as e:
            known = next((v for v in pv.voices_map().values() if v.get("id") == voice["id"] and v.get("owner")), None)
            if "voice" in str(e).lower() and known and i == 0:
                say(f"giọng chưa có trong tài khoản, đang thêm từ thư viện ({known.get('name')})…")
                pv.el_add_voice(known["owner"], voice["id"], known.get("name") or voice["id"])
                r = _speak(text, voice, target, model, lang, vs, seed, args.timestamps)
            else:
                raise
        usd = pv.tts_usd(r["chars"], model)
        info = {"file": rel(target), "chars": r["chars"], "usd": usd, "seconds": duration_of(target)}
        if args.timestamps and r.get("alignment"):
            align = target.with_suffix(target.suffix + ".alignment.json")
            align.write_text(json.dumps({**r["alignment"], "words": _words(r["alignment"])}, ensure_ascii=False),
                             encoding="utf-8")
            info["alignment"] = rel(align)
        ledger.add({"kind": "tts", "provider": "elevenlabs", "model": model, "what": args.what or "narration",
                    "voice": voice.get("name") or voice["id"], "units": r["chars"], "unit": "characters", "usd": usd,
                    "estimated": True, "files": [rel(target)], "request_id": r.get("request_id")})
        say(f"✓ {info['file']} · {info['seconds'] or '?'} s · {r['chars']:,} ký tự · ${usd:.3f}")
        files.append(info)
    say(f"Dự án đã tiêu ${ledger.spent():.2f}" + (f" / ${ledger.budget():.2f}" if ledger.budget() is not None else ""))
    result({"files": files, "spent_usd": ledger.spent()})


def cmd_sfx(args, ledger: Ledger) -> None:
    seconds = args.seconds
    est = round((seconds or 5) / 60 * pv.SFX_USD_PER_MIN, 4)
    ledger.guard(est, args.over_budget)
    out = Path(args.out)
    r = pv.el_sfx(args.prompt, seconds, out, args.influence)
    secs = duration_of(out) or seconds or 5
    usd = round(secs / 60 * pv.SFX_USD_PER_MIN, 4)
    ledger.add({"kind": "sfx", "provider": "elevenlabs", "model": "sound-generation", "what": args.what or args.prompt[:60],
                "units": round(secs, 2), "unit": "seconds", "usd": usd, "estimated": True, "files": [rel(out)],
                "request_id": r.get("request_id")})
    say(f"✓ {rel(out)} · {secs:.1f} s · ${usd:.3f}")
    result({"file": rel(out), "seconds": secs, "usd": usd, "spent_usd": ledger.spent()})


# ---------------------------------------------------------------- fal: parameters
_SIZES = {"1:1": "square_hd", "4:3": "landscape_4_3", "3:2": "landscape_4_3", "16:9": "landscape_16_9",
          "21:9": "landscape_16_9", "3:4": "portrait_4_3", "2:3": "portrait_4_3", "9:16": "portrait_16_9"}
_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}


def _coerce(prop: dict, value, name: str):
    typ, enum = prop.get("type"), prop.get("enum")
    if enum and not isinstance(value, (dict, list)):
        if value in enum:
            return value
        if str(value) in [str(x) for x in enum]:
            return next(x for x in enum if str(x) == str(value))
        nums = [x for x in enum if str(x).replace(".", "", 1).isdigit()]
        if nums and str(value).replace(".", "", 1).isdigit():          # durations: the nearest allowed value
            best = min(nums, key=lambda x: abs(float(x) - float(value)))
            say(f"  {name}={value} không có trong model, dùng {best}")
            return best
        fail(f"{name}={value!r} không hợp lệ cho model này; chọn một trong: {enum}")
    if typ == "integer":
        return int(float(value))
    if typ == "number":
        return float(value)
    if typ == "boolean":
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
    if typ == "string" and not isinstance(value, str):
        return str(value)
    return value


def _put(payload: dict, props: dict, names, value, label: str, *, required: bool = False) -> bool:
    for n in ([names] if isinstance(names, str) else names):
        if n in props:
            payload[n] = _coerce(props[n], value, n)
            return True
    if required:
        fail(f"model không có tham số cho {label} (tham số có: {', '.join(props)})")
    say(f"  bỏ qua {label}: model không có tham số này")
    return False


def _parse_value(v: str):
    if v.startswith("@"):
        return pv.data_uri(Path(v[1:]))
    try:
        return json.loads(v)
    except ValueError:
        return v


def _apply_sets(payload: dict, props: dict, sets: list[str] | None, files: list[str] | None, lists: list[str] | None) -> None:
    for item in sets or []:
        k, _, v = item.partition("=")
        payload[k.strip()] = _coerce(props.get(k.strip(), {}), _parse_value(v), k.strip()) if k.strip() in props else _parse_value(v)
    for item in files or []:
        k, _, v = item.partition("=")
        payload[k.strip()] = pv.data_uri(Path(v.strip()))
    for item in lists or []:
        k, _, v = item.partition("=")
        payload[k.strip()] = [pv.data_uri(Path(x.strip())) for x in v.split(",") if x.strip()]


def _estimate(ep: str, payload: dict, outputs: list[dict] | None = None) -> tuple[float | None, str]:
    """USD of a call from fal's unit price: per image, per second of video, per megapixel, or per call."""
    if not pv.has_key("fal_api_key"):
        return None, "chưa có key fal nên chưa tính được giá"
    price = pv.fal_price(ep)
    n = len(outputs) if outputs else int(payload.get("num_images") or payload.get("num_outputs") or 1)
    if price and price.get("unit_price") is not None:
        up, unit = float(price["unit_price"]), str(price.get("unit") or "").lower()
        if "image" in unit:
            return round(up * n, 4), f"{n} × ${up}/{unit}"
        if "second" in unit:
            secs = None
            if outputs:
                secs = next((float(o["duration"]) for o in outputs if o.get("duration")), None)
            if secs is None:
                try:
                    secs = float(str(payload.get("duration") or 5).rstrip("s"))
                except ValueError:
                    secs = 5.0
            return round(up * secs, 4), f"{secs:g} s × ${up}/{unit}"
        if "megapixel" in unit:
            if outputs and all(o.get("width") and o.get("height") for o in outputs):
                mp = sum(o["width"] * o["height"] for o in outputs) / 1e6
            else:
                mp = n * {"1K": 1.0, "2K": 4.2, "4K": 16.8}.get(str(payload.get("resolution") or "1K"), 1.0)
            return round(up * mp, 4), f"{mp:.2f} MP × ${up}/{unit}"
        if unit in ("video", "videos", "request", "requests", "call", "calls", "generation", "generations", "run", "unit", "units"):
            return round(up, 4), f"${up}/{unit}"
    hist = pv.fal_estimate_call(ep)
    if hist is not None:
        return round(hist * (n if "image" in ep or "text-to-image" in ep else 1), 4), "trung bình theo lịch sử fal"
    return None, "fal không có giá cho model này"


def _save_outputs(outputs: list[dict], out: Path) -> list[Path]:
    saved = []
    for i, o in enumerate(outputs):
        url = o["url"]
        ext = out.suffix or Path(url.split("?")[0]).suffix or {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
                                                                 "video/mp4": ".mp4", "audio/mpeg": ".mp3",
                                                                 "audio/wav": ".wav"}.get(o.get("content_type") or "", "")
        target = (out if len(outputs) == 1 else out.with_name(f"{out.stem}_{i + 1}{ext}"))
        if not target.suffix and ext:
            target = target.with_suffix(ext)
        if url.startswith("data:"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        else:
            pv.download(url, target)
        saved.append(target)
    return saved


def _run_fal(ep: str, payload: dict, out: Path, kind: str, args, ledger: Ledger, schema: dict) -> None:
    missing = [r for r in schema.get("required") or [] if r not in payload]
    if missing:
        fail(f"thiếu tham số bắt buộc của {ep}: {', '.join(missing)}")
    est, how = _estimate(ep, payload)
    say(f"{ep} · ước tính " + (f"${est:.3f} ({how})" if est is not None else how))
    if args.dry_run:                                    # spends nothing: only say whether the real call would pass
        budget = ledger.budget()
        if budget is not None and ledger.spent() + (est or 0) > budget:
            say(f"  (chạy thật sẽ bị chặn: đã tiêu ${ledger.spent():.2f}, ngân sách ${budget:.2f})")
        say("Thử (không gửi): " + json.dumps(_short(payload), ensure_ascii=False))
        result({"dry_run": True, "endpoint": ep, "payload": _short(payload), "est_usd": est})
        return
    ledger.guard(est, args.over_budget)
    started = time.time()
    sub = pv.fal_submit(ep, payload)
    say(f"  đã gửi, request {sub.get('request_id')}")
    data = pv.fal_wait(sub, timeout=args.timeout, on_status=lambda s, st: say(
        f"  {s}" + (f" (vị trí {st.get('queue_position')})" if s == "IN_QUEUE" and st.get("queue_position") is not None else "")))
    outputs = pv.media_outputs(data)
    if not outputs:
        fail(f"model không trả file nào: {json.dumps(data, ensure_ascii=False)[:400]}")
    saved = _save_outputs(outputs, out)
    usd, how = _estimate(ep, payload, outputs)
    ledger.add({"kind": kind, "provider": "fal", "model": ep, "what": args.what or out.stem, "usd": usd or 0,
                "estimated": True, "basis": how, "files": [rel(p) for p in saved], "request_id": sub.get("request_id")})
    for p, o in zip(saved, outputs):
        size = f"{o['width']}×{o['height']}" if o.get("width") else ""
        say(f"✓ {rel(p)} {size}".rstrip())
    if isinstance(data, dict) and data.get("description"):
        say(f"  model ghi: {str(data['description'])[:200]}")
    say(f"Xong sau {time.time() - started:.0f} s · ${usd or 0:.3f} ({how}) · dự án đã tiêu ${ledger.spent():.2f}"
        + (f" / ${ledger.budget():.2f}" if ledger.budget() is not None else ""))
    result({"files": [rel(p) for p in saved], "usd": usd, "request_id": sub.get("request_id"), "spent_usd": ledger.spent()})


# ---------------------------------------------------------------- images straight from OpenAI / Google
_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def _write_image(data: bytes, mime: str, target: Path) -> Path:
    """Save as the extension asked for; convert with ffmpeg when the API returned another format."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if data[:8] == b"\x89PNG\r\n\x1a\n":                  # trust the bytes over the declared type
        mime = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    got = _EXT.get(mime, ".png")
    if not target.suffix:
        target = target.with_suffix(got)
    if _FORMATS.get(target.suffix.lower()) == _FORMATS.get(got):
        target.write_bytes(data)
        return target
    tmp = target.with_suffix(got)
    tmp.write_bytes(data)
    ffmpeg = _tools("ffmpeg")
    if not ffmpeg:
        say(f"  model trả {got}, không có ffmpeg để đổi sang {target.suffix}: giữ {tmp.name}")
        return tmp
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(tmp), str(target)], check=True)
    tmp.unlink(missing_ok=True)
    return target


def _openai_size(aspect: str | None, resolution: str | None) -> str | None:
    if not aspect:
        return None                                     # the API picks ("auto")
    if "x" in aspect:
        return aspect
    try:
        w, h = (float(x) for x in aspect.split(":"))
    except ValueError:
        fail(f"tỉ lệ {aspect!r} không đọc được (VD 16:9 hoặc 1536x1024)")
    if resolution in ("2K", "4K"):
        long = {"2K": 2048, "4K": 3840}[resolution]
        W, H = (long, long * h / w) if w >= h else (long * w / h, long)
        return f"{int(round(W / 16) * 16)}x{int(round(H / 16) * 16)}"
    return "1024x1024" if w == h else ("1536x1024" if w > h else "1024x1536")


def _image_direct(ep: str, prompt: str, refs: list[Path], args, ledger: Ledger) -> None:
    provider, model = ep.split(":", 1)
    out = Path(args.out)
    n = max(1, args.n or 1)
    extra = {}
    for item in args.set or []:
        k, _, v = item.partition("=")
        extra[k.strip()] = _parse_value(v)
    if args.file or args.files:
        say("  bỏ qua --file/--files: chỉ dùng cho model fal (ảnh tham chiếu dùng --ref)")
    if provider == "openai":
        size = _openai_size(args.aspect, args.resolution)
        quality = args.quality
        fmt = _FORMATS.get(out.suffix.lower())
        scale = 1.0
        if size and "x" in size:
            w, _, h = size.partition("x")
            scale = max(1.0, int(w) * int(h) / (1024 * 1024))
        ratio = pv.OPENAI_IMAGE_MODELS.get(model, (0, 0, 30.0))[2] / 30.0      # table is for $30 / 1M output tokens
        est = round(pv.OPENAI_QUALITY_USD.get(quality or "auto", 0.17) * scale * ratio * n, 4)
        how = f"ước tính theo chất lượng {quality or 'auto'}, chi phí thật tính từ token OpenAI trả về"
        request_view = {"model": model, "prompt": prompt[:80], "size": size, "quality": quality, "n": n,
                        "output_format": fmt, "refs": [r.name for r in refs], **extra}
    elif provider == "google":
        if args.aspect and args.aspect not in pv.GOOGLE_ASPECTS:
            fail(f"tỉ lệ {args.aspect} không có ở Gemini; chọn: {', '.join(pv.GOOGLE_ASPECTS)}")
        if args.resolution and args.resolution not in pv.GOOGLE_SIZES:
            fail(f"resolution {args.resolution} không có ở Gemini; chọn: {', '.join(pv.GOOGLE_SIZES)}")
        if args.quality:
            say("  bỏ qua --quality: Gemini không có tham số này (dùng --resolution)")
        per = pv.google_usd(model, args.resolution)
        est = round(per * n, 4) if per is not None else None
        how = f"{n} × ${per}/ảnh {args.resolution or '1K'}" if per is not None else "chưa có bảng giá cho model này"
        request_view = {"model": model, "prompt": prompt[:80], "aspectRatio": args.aspect, "imageSize": args.resolution,
                        "n": n, "refs": [r.name for r in refs], **extra}
    else:
        fail(f"không biết nhà cung cấp {provider!r} (dùng openai: hoặc google:)")
    say(f"{provider} {model} · ước tính " + (f"${est:.3f} ({how})" if est is not None else how))
    if args.dry_run:
        budget = ledger.budget()
        if budget is not None and ledger.spent() + (est or 0) > budget:
            say(f"  (chạy thật sẽ bị chặn: đã tiêu ${ledger.spent():.2f}, ngân sách ${budget:.2f})")
        say("Thử (không gửi): " + json.dumps(request_view, ensure_ascii=False))
        result({"dry_run": True, "endpoint": ep, "request": request_view, "est_usd": est})
        return
    ledger.guard(est, args.over_budget)
    started = time.time()
    note = ""
    if provider == "openai":
        r = pv.openai_image(model, prompt, refs, size=size, quality=quality, n=n, output_format=fmt, extra=extra,
                            timeout=args.timeout)
        images, usd, exact = r["images"], r["usd"], r["usd"] is not None
        usd = usd if exact else est
        if r.get("usage"):
            note = f"{r['usage'].get('output_tokens')} token ảnh ra"
    else:
        images = []
        for i in range(n):
            r = pv.google_image(model, prompt, refs, aspect=args.aspect, size=args.resolution, extra=extra, timeout=args.timeout)
            images += r["images"][:1]
            if r.get("text"):
                note = r["text"][:200]
        usd, exact = (round(per * len(images), 4) if per is not None else None), per is not None
    saved = [_write_image(data, mime, out if len(images) == 1 else out.with_name(f"{out.stem}_{i + 1}{out.suffix}"))
             for i, (data, mime) in enumerate(images)]
    ledger.add({"kind": "image", "provider": provider, "model": model, "what": args.what or out.stem, "usd": usd or 0,
                "estimated": not exact, "files": [rel(p) for p in saved]})
    for p in saved:
        say(f"✓ {rel(p)}")
    if note:
        say(f"  {note}")
    say(f"Xong sau {time.time() - started:.0f} s · ${usd or 0:.3f} · dự án đã tiêu ${ledger.spent():.2f}"
        + (f" / ${ledger.budget():.2f}" if ledger.budget() is not None else ""))
    result({"files": [rel(p) for p in saved], "usd": usd, "spent_usd": ledger.spent()})


# ---------------------------------------------------------------- images through gemini.google.com (the user's plan)
def _size_of(path: Path) -> tuple[int, int] | None:
    probe = _tools("ffprobe")
    if not probe:
        return None
    try:
        out = subprocess.run([probe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60).stdout.strip()
        w, h = (int(x) for x in out.split(",")[:2])
        return w, h
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _delogo(path: Path) -> bool:
    """Blur the Gemini mark of the bottom-right corner (box from gemini_web selectors["watermark"])."""
    from . import gemini_web
    ffmpeg, size = _tools("ffmpeg"), _size_of(path)
    if not ffmpeg or not size:
        return False
    w, h = size
    right, bottom, box = gemini_web.selectors()["watermark"]
    s = min(w, h)
    bw = max(8, int(s * box))
    x, y = min(w - bw - 2, int(w - s * right)), min(h - bw - 2, int(h - s * bottom))
    tmp = path.with_name(path.stem + ".delogo" + path.suffix)
    try:
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf", f"delogo=x={x}:y={y}:w={bw}:h={bw}",
                        "-frames:v", "1", str(tmp)], check=True, timeout=120)
        tmp.replace(path)
        return True
    except (OSError, subprocess.SubprocessError):
        tmp.unlink(missing_ok=True)
        return False


def _image_web(ep: str, prompt: str, refs: list[Path], args, ledger: Ledger) -> bool:
    """gemini-web:<mode>. False = it failed and gemini_web_fallback names a model to use instead."""
    from . import gemini_web
    mode = ep[len(pv.WEB):].strip()
    out = Path(args.out)
    n = max(1, args.n or 1)
    say(f"gemini-web {mode or '(chế độ đang chọn)'} · $0 (gói Gemini của tài khoản) · {n} ảnh"
        + (f" · {len(refs)} ảnh tham chiếu" if refs else ""))
    if args.quality or args.resolution or args.set:
        say("  bỏ qua --quality/--resolution/--set: Gemini web không có các tham số này")
    if args.dry_run:
        result({"dry_run": True, "endpoint": ep, "request": {"mode": mode, "prompt": prompt[:80], "aspect": args.aspect,
                                                             "n": n, "refs": [r.name for r in refs]}, "est_usd": 0})
        return True
    started = time.time()
    try:
        images = gemini_web.generate(prompt, refs, mode=mode, aspect=args.aspect, n=n,
                                     timeout=min(args.timeout, 600), say=say)
    except gemini_web.GeminiWebError as e:
        fallback = (db.get_setting("gemini_web_fallback") or "").strip()
        if fallback and not pv.endpoint(fallback).startswith(pv.WEB) and e.code != "refused":
            say(f"  Gemini web lỗi ({e}); chuyển sang {fallback} theo Cài đặt (tốn tiền API)")
            return False
        fail(f"Gemini web: {e}" + (" · Cài đặt có thể đặt gemini_web_fallback để tự chuyển sang API" if e.code == "quota" else ""),
             code={"login": 2, "quota": 4}.get(e.code, 1))
    saved = [_write_image(data, mime, out if len(images) == 1 else out.with_name(f"{out.stem}_{i + 1}{out.suffix}"))
             for i, (data, mime) in enumerate(images)]
    if db.get_setting("gemini_web_delogo") == "1":
        cleaned = sum(_delogo(p) for p in saved)
        if cleaned:
            say(f"  đã làm mờ logo Gemini ở góc {cleaned} ảnh")
    ledger.add({"kind": "image", "provider": "gemini-web", "model": mode or "default", "what": args.what or out.stem,
                "usd": 0, "estimated": False, "files": [rel(p) for p in saved]})
    for p in saved:
        say(f"✓ {rel(p)}")
    say(f"Xong sau {time.time() - started:.0f} s · $0 · dự án đã tiêu ${ledger.spent():.2f}")
    result({"files": [rel(p) for p in saved], "usd": 0, "spent_usd": ledger.spent()})
    return True


def cmd_gemini_web(args) -> None:
    from . import gemini_web
    try:
        if args.action == "login":
            r = gemini_web.login(say=say)
            say(f"Đã đóng cửa sổ. Hồ sơ: {r['profile']}")
        else:
            r = gemini_web.status(args.mode)
            say(("✓ đã đăng nhập" + (f" · chế độ đang chọn: {r['mode']}" if r.get("mode") else "")) if r["ok"]
                else f"✕ {r['error']}")
    except gemini_web.GeminiWebError as e:
        r = {"ok": False, "error": str(e), "code": e.code}
        say(f"✕ {e}")
    result(r)


# ---------------------------------------------------------------- fal: commands
def cmd_image(args, ledger: Ledger) -> None:
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip() if args.prompt_file else (args.prompt or "").strip()
    if not prompt:
        fail("chưa có prompt (--prompt hoặc --prompt-file)")
    refs = [Path(r) for r in args.ref or []]
    for r in refs:
        if not r.is_file():
            fail(f"không thấy ảnh tham chiếu {r}")
    ep = pv.endpoint(args.model or ("edit" if refs else "draft" if args.draft else "main"))
    if ep.startswith(pv.WEB):
        if _image_web(ep, prompt, refs, args, ledger):
            return
        ep = pv.endpoint(db.get_setting("gemini_web_fallback"))
    if ep.startswith(pv.DIRECT):
        _image_direct(ep, prompt, refs, args, ledger)
        return
    schema = pv.fal_schema(ep)
    props = schema["props"]
    out = Path(args.out)
    payload: dict = {}
    _put(payload, props, "prompt", prompt, "prompt", required=True)
    if refs:
        if "image_urls" in props:
            payload["image_urls"] = [pv.data_uri(r) for r in refs]
        elif len(refs) == 1:
            _put(payload, props, ("image_url", "reference_image_url", "input_image_url"), pv.data_uri(refs[0]), "ảnh tham chiếu",
                 required=True)
        else:
            fail(f"{ep} chỉ nhận một ảnh tham chiếu")
    if args.aspect:
        if "aspect_ratio" in props:
            _put(payload, props, "aspect_ratio", args.aspect, "aspect")
        elif "image_size" in props:
            if "x" in args.aspect:
                w, _, h = args.aspect.partition("x")
                payload["image_size"] = {"width": int(w), "height": int(h)}
            else:
                payload["image_size"] = _SIZES.get(args.aspect) or fail(f"tỉ lệ {args.aspect} chưa hỗ trợ cho {ep}: dùng WxH")
        else:
            say("  bỏ qua aspect: model không có tham số tỉ lệ")
    if args.quality:
        _put(payload, props, "quality", args.quality, "quality")
    if args.resolution:
        _put(payload, props, "resolution", args.resolution, "resolution")
    if args.n and args.n > 1:
        _put(payload, props, ("num_images", "num_outputs"), args.n, "số ảnh")
    fmt = _FORMATS.get(out.suffix.lower())
    if fmt and "output_format" in props:
        payload["output_format"] = _coerce(props["output_format"], fmt, "output_format")
    _apply_sets(payload, props, args.set, args.file, args.files)
    _run_fal(ep, payload, out, "image", args, ledger, schema)


def cmd_video(args, ledger: Ledger) -> None:
    ep = pv.endpoint(args.model or "video")
    schema = pv.fal_schema(ep)
    props = schema["props"]
    payload: dict = {}
    if args.prompt:
        _put(payload, props, "prompt", args.prompt, "prompt")
    if args.image:
        _put(payload, props, ("start_image_url", "image_url", "first_frame_url", "first_frame_image_url"),
             pv.data_uri(Path(args.image)), "ảnh đầu", required=True)
    if args.end:
        _put(payload, props, ("end_image_url", "last_frame_url", "last_frame_image_url", "tail_image_url"),
             pv.data_uri(Path(args.end)), "ảnh cuối", required=True)
    if args.seconds:
        _put(payload, props, ("duration", "duration_seconds"), args.seconds, "thời lượng")
    if "generate_audio" in props:
        payload["generate_audio"] = bool(args.audio)          # films mix their own sound: off unless asked
    if args.resolution:
        _put(payload, props, "resolution", args.resolution, "resolution")
    if args.aspect:
        _put(payload, props, "aspect_ratio", args.aspect, "aspect")
    _apply_sets(payload, props, args.set, args.file, args.files)
    _run_fal(ep, payload, Path(args.out), "video", args, ledger, schema)


def cmd_run(args, ledger: Ledger) -> None:
    ep = pv.endpoint(args.endpoint)
    schema = pv.fal_schema(ep)
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8")) if args.input_json else {}
    _apply_sets(payload, schema["props"], args.set, args.file, args.files)
    _run_fal(ep, payload, Path(args.out), args.kind, args, ledger, schema)


def cmd_schema(args) -> None:
    ep = pv.endpoint(args.endpoint)
    if ep.startswith("openai:"):
        say(f"{ep} (OpenAI Images API): --prompt, --ref (ảnh để sửa, tối đa 16), --aspect 1:1|3:2|16:9… hoặc WxH "
            "(→ size 1024x1024, 1536x1024, 1024x1536; kèm --resolution 2K|4K thì tính WxH lớn), "
            "--quality low|medium|high|xhigh|max|auto, --n, đuôi --out quyết định output_format; "
            "--set background=transparent|opaque, --set moderation=low, --set output_compression=80")
        return
    if ep.startswith("google:"):
        say(f"{ep} (Gemini generateContent): --prompt, --ref (ảnh tham chiếu, tối đa ~14), "
            f"--aspect {'|'.join(pv.GOOGLE_ASPECTS)}, --resolution {'|'.join(pv.GOOGLE_SIZES)}, --n (mỗi ảnh một lần gọi); "
            "--set khóa=giá_trị thêm vào imageConfig")
        return
    s = pv.fal_schema(ep)
    say(f"{ep}: tham số (* = bắt buộc)")
    for name, p in s["props"].items():
        enum = f" ∈ {p['enum']}" if p.get("enum") else ""
        default = f" = {p['default']!r}" if p.get("default") not in (None, "") else ""
        say(f"  {'*' if name in s['required'] else ' '}{name}: {p.get('type') or '?'}{enum}{default} · {p.get('description', '')[:110]}")


def cmd_models(args) -> None:
    for m in pv.fal_search(args.q or "", args.category or "", args.limit):
        say(f"{m['endpoint']} | {m['name']} | {m['category']} | {m['date']}")


def cmd_price(args) -> None:
    ep = pv.endpoint(args.endpoint)
    if ep.startswith("openai:"):
        p = pv.OPENAI_IMAGE_MODELS.get(ep[7:])
        say(f"{ep}: " + (f"token chữ vào ${p[0]}/1M · ảnh vào ${p[1]}/1M · ảnh ra ${p[2]}/1M · khoảng "
                         + ", ".join(f"{q} ${v}" for q, v in pv.OPENAI_QUALITY_USD.items()) + " cho ảnh 1024×1024"
                         if p else "chưa có trong bảng giá của app"))
        result({"endpoint": ep, "per_million_tokens": p})
        return
    if ep.startswith(pv.WEB):
        say(f"{ep}: $0 · dùng lượt ảnh của gói Gemini trên tài khoản (có hạn mức mỗi ngày)")
        result({"endpoint": ep, "per_image": 0})
        return
    if ep.startswith("google:"):
        t = pv.GOOGLE_IMAGE_MODELS.get(ep[7:])
        say(f"{ep}: " + (", ".join(f"{k} ${v}/ảnh" for k, v in t.items()) if t else "chưa có trong bảng giá của app"))
        result({"endpoint": ep, "per_image": t})
        return
    p = pv.fal_price(ep)
    hist = pv.fal_estimate_call(ep)
    say(f"{ep}: " + (f"${p['unit_price']} / {p['unit']}" if p else "fal không có giá đơn vị")
        + (f" · trung bình một lần gọi ${hist:.4f}" if hist is not None else ""))
    result({"endpoint": ep, "price": p, "avg_call_usd": hist})


def cmd_cost(args, ledger: Ledger) -> None:
    if not ledger.path:
        fail("không ở trong thư mục dự án (không thấy project.json)")
    data = ledger._read()
    by_kind: dict[str, float] = {}
    for e in data.get("events") or []:
        by_kind[e.get("kind") or "?"] = by_kind.get(e.get("kind") or "?", 0) + float(e.get("usd") or 0)
    say(f"Đã tiêu ${ledger.spent():.2f}" + (f" / ngân sách ${ledger.budget():.2f}" if ledger.budget() is not None else "")
        + " · " + ", ".join(f"{k} ${v:.2f}" for k, v in sorted(by_kind.items())))
    result({"spent_usd": ledger.spent(), "budget_usd": ledger.budget(), "by_kind": by_kind})


# ---------------------------------------------------------------- CLI
def _common(p, paid: bool = True) -> None:
    p.add_argument("--project", help="thư mục dự án (mặc định: tìm project.json từ thư mục hiện tại trở lên)")
    if paid:
        p.add_argument("--what", help="tên mục trong nhật ký chi phí (key của ảnh, id của câu...)")
        p.add_argument("--over-budget", action="store_true", help="cho phép vượt ngân sách (chỉ khi người dùng đã đồng ý)")


def _fal_args(p) -> None:
    p.add_argument("--set", action="append", metavar="K=V", help="tham số thêm (JSON hoặc chữ; @file = gửi file)")
    p.add_argument("--file", action="append", metavar="K=PATH", help="tham số là một file")
    p.add_argument("--files", action="append", metavar="K=A,B", help="tham số là danh sách file")
    p.add_argument("--dry-run", action="store_true", help="in yêu cầu và ước tính, không gửi")
    p.add_argument("--timeout", type=int, default=1800, help="giây chờ tối đa")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="gen.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    _common(sub.add_parser("check", help="key, gói ElevenLabs, số dư fal"), paid=False)

    p = sub.add_parser("voices", help="thư viện giọng ElevenLabs")
    p.add_argument("--lang"); p.add_argument("--q"); p.add_argument("--gender", choices=["male", "female", "neutral"])
    p.add_argument("--limit", type=int, default=30); p.add_argument("--mine", action="store_true")
    p.add_argument("--add", metavar="VOICE_ID"); p.add_argument("--owner"); p.add_argument("--name")
    _common(p, paid=False)

    p = sub.add_parser("tts", help="lời dẫn bằng ElevenLabs")
    p.add_argument("--text"); p.add_argument("--text-file"); p.add_argument("--out", required=True)
    p.add_argument("--voice", help="voice id (mặc định: giọng của ngôn ngữ dự án)"); p.add_argument("--model")
    p.add_argument("--lang", help="mã ngôn ngữ ISO 639-1 (mặc định: ngôn ngữ dự án)")
    p.add_argument("--stability", type=float, default=0.4); p.add_argument("--similarity", type=float, default=0.8)
    p.add_argument("--style", type=float); p.add_argument("--speed", type=float)
    p.add_argument("--seed", type=int); p.add_argument("--takes", type=int, default=1)
    p.add_argument("--timestamps", action="store_true", help="ghi thêm <out>.alignment.json (thời điểm từng ký tự, từng chữ)")
    _common(p)

    p = sub.add_parser("sfx", help="hiệu ứng âm thanh bằng ElevenLabs")
    p.add_argument("--prompt", required=True); p.add_argument("--seconds", type=float); p.add_argument("--influence", type=float)
    p.add_argument("--out", required=True)
    _common(p)

    p = sub.add_parser("image", help="ảnh bằng fal")
    p.add_argument("--prompt"); p.add_argument("--prompt-file"); p.add_argument("--out", required=True)
    p.add_argument("--model", help="main | draft | edit | alias fal (gpt, gpt-edit, nano-pro, nano2, seedream) | "
                                   "trực tiếp (openai, openai-flare, openai-mini, gemini-pro, gemini-flash, gemini-lite) | "
                                   "gemini-web (gói Gemini qua trình duyệt, $0) | "
                                   "id model fal | openai:<model> | google:<model> | gemini-web:<chế độ>")
    p.add_argument("--draft", action="store_true", help="dùng model ảnh rẻ")
    p.add_argument("--ref", action="append", help="ảnh tham chiếu / ảnh gốc để sửa (lặp lại được)")
    p.add_argument("--aspect"); p.add_argument("--quality"); p.add_argument("--resolution"); p.add_argument("--n", type=int, default=1)
    _fal_args(p); _common(p)

    p = sub.add_parser("video", help="video bằng fal (mặc định ảnh → video)")
    p.add_argument("--image"); p.add_argument("--end"); p.add_argument("--prompt"); p.add_argument("--out", required=True)
    p.add_argument("--model"); p.add_argument("--seconds", type=float); p.add_argument("--resolution"); p.add_argument("--aspect")
    p.add_argument("--audio", action="store_true", help="để model tạo tiếng (tốn thêm; phim tự trộn tiếng nên mặc định tắt)")
    _fal_args(p); _common(p)

    p = sub.add_parser("run", help="gọi bất kỳ model nào của fal")
    p.add_argument("endpoint"); p.add_argument("--out", required=True); p.add_argument("--input-json")
    p.add_argument("--kind", default="fal", help="loại trong nhật ký chi phí (image, video, audio, upscale...)")
    _fal_args(p); _common(p)

    p = sub.add_parser("schema", help="tham số của một model fal"); p.add_argument("endpoint")
    p = sub.add_parser("models", help="tìm model trên fal")
    p.add_argument("--q"); p.add_argument("--category"); p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("gemini-web", help="hồ sơ Chrome của Gemini web: login (mở cửa sổ để đăng nhập) | status")
    p.add_argument("action", choices=["login", "status"]); p.add_argument("--mode", choices=["hidden", "headless", "show"])
    p = sub.add_parser("price", help="giá của một model fal"); p.add_argument("endpoint")
    _common(sub.add_parser("cost", help="chi phí dự án so với ngân sách"), paid=False)
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    project = Path(args.project).resolve() if getattr(args, "project", None) else find_project(Path.cwd())
    ledger = Ledger(project)
    paid = {"tts": cmd_tts, "sfx": cmd_sfx, "image": cmd_image, "video": cmd_video, "run": cmd_run, "cost": cmd_cost}
    free = {"check": cmd_check, "voices": cmd_voices, "schema": cmd_schema, "models": cmd_models, "price": cmd_price,
            "gemini-web": cmd_gemini_web}
    try:
        if args.cmd in paid:
            paid[args.cmd](args, ledger)
        else:
            free[args.cmd](args)
    except ApiError as e:
        fail(str(e), code=2 if e.code == "no_key" else 1)
    except subprocess.CalledProcessError as e:
        fail(f"lệnh {e.cmd[0]} lỗi (mã {e.returncode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
