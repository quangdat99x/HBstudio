"""Render a thumbnail image with GPT Image through Creater Vid's asset generator (its OpenAI key, never printed).

  gpt_image.py --prompt "..." | --prompt-file F   --out center_ai.png
               [--model openai:gpt-image-2.5-sunburst] [--aspect 2:3] [--quality high] [--ref img.png ...]
               [--dry-run]

Portrait 2:3 (1024x1536) fits the centre slot of the JRE template; then place it like a real photo:
  py -3.14 -X utf8 E:\\Tool\\jre-thumb\\frames.py fill --img center_ai.png --plan thumb_plan.json
Each paid call is appended to costs_gpt_image.json next to --out (model, USD, file).
Run: py -3.14 -X utf8 E:\\Tool\\jre-thumb\\gpt_image.py --prompt-file prompt.txt --out DIR\\center_ai.png
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

CREATER = Path(__file__).resolve().parent.parent / "Creater Vid"
CREATER_PY = CREATER / ".venv" / "Scripts" / "python.exe"
GEN_PY = CREATER / "gen.py"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="openai:gpt-image-2.5-sunburst")
    ap.add_argument("--aspect", default="2:3")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip() if args.prompt_file else (args.prompt or "").strip()
    if not prompt:
        print("LỖI: chưa có prompt (--prompt hoặc --prompt-file)")
        return 1
    if not CREATER_PY.is_file() or not GEN_PY.is_file():
        print(f"LỖI: không thấy Creater Vid ({GEN_PY})")
        return 1
    pfile = out.with_suffix(".prompt.txt")
    pfile.write_text(prompt, encoding="utf-8")
    cmd = [str(CREATER_PY), "-X", "utf8", str(GEN_PY), "image", "--prompt-file", str(pfile), "--out", str(out),
           "--model", args.model, "--aspect", args.aspect, "--what", f"jre-thumb {out.stem}"]
    if args.quality and not args.model.startswith("google:"):
        cmd += ["--quality", args.quality]
    for r in args.ref:
        cmd += ["--ref", str(Path(r).resolve())]
    if args.dry_run:
        cmd.append("--dry-run")
    started = time.time()
    # cwd = the output folder: no project.json above it, so gen.py keeps no film budget/ledger for this call
    p = subprocess.run(cmd, cwd=out.parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=1900)
    res = {}
    for line in (p.stdout or "").splitlines():
        if line.startswith("RESULT "):
            res = json.loads(line[7:])
        else:
            print(line)
    if p.returncode:
        print((p.stderr or "").strip()[-1500:])
        print(f"LỖI: gen.py thoát mã {p.returncode}")
        return p.returncode
    if args.dry_run:
        return 0
    if not out.is_file():
        print("LỖI: gen.py chạy xong nhưng không có file ảnh")
        return 1
    log = out.parent / "costs_gpt_image.json"
    try:
        events = json.loads(log.read_text(encoding="utf-8")) if log.is_file() else []
    except ValueError:
        events = []
    events.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "model": args.model, "quality": args.quality,
                   "aspect": args.aspect, "usd": res.get("usd"), "file": out.name, "sec": round(time.time() - started)})
    log.write_text(json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {out} · ${res.get('usd') or 0:.3f} · {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
