"""JRE thumbnail helper: frame candidates for picking Joe / guest expressions.

  sheet  <video> --start S --end E [--step 1.5] [--out DIR]
         -> DIR/sheet_01.jpg ... (5x4 grid, each cell labelled with its time
            in seconds of the SOURCE video) + DIR/index.json
  grab   <video> --t T [--t T ...] [--out DIR]
         -> DIR/frame_<T>.png at full resolution (exact time, re-decoded)
            + DIR/frame_<T>_grid.jpg (100px coordinate grid, to read the face box)
  Template DAHVNt9L56k geometry is built in, so --panel/--center/--frame are optional.
  Plan flow (no Canva needed): crop --img --plan (left, right) + fill --plan (center)
  -> thumb_plan.json -> mock --plan -> show the user -> on approval apply the plan on Canva.
  An AI centre image is rendered with gpt_image.py (GPT Image via Creater Vid) and placed with fill like a
  photo; a plan with only "center_ai_prompt" (older runs) shows a placeholder in the mock.
  fill   --img IMG [--slot center] [--focus FX,FY] [--zoom 1] [--plan P]
         -> imageBox that covers the element with the focus point centred.
  crop   --head X1,Y1,X2,Y2 --side left|right [--img FRAME --plan P]
         [--panel L,T,W,H] [--center CL,CT,CW,CH]
         [--src 1920x1080] [--head-h 700] [--margin 15] [--head-top 40]
         -> JSON imageBox {left, top, width, height} for Canva crop_media + a
            CHECK of where the head lands on the page. The WHOLE head box
            (hair to chin, ear to ear) is fitted inside the strip of the side
            panel that the centre panel does NOT cover, with `margin` px spare;
            exit code 2 + "OVERLAP" if it still touches the centre panel.
  mock   --plan P | --layer IMG,L,T,W,H,BL,BT,BW,BH [--layer ...]  [--frame CL,CT,CW,CH] --out F.jpg
         -> full-res 1920x1080 render of the layout (layers in order, each image
            scaled to imageBox BW x BH at BL,BT inside element L,T,W,H) + green
            frame + 4K badge, so the composition can be checked at real size before commit.
  verify --export F.jpg --mock mock.jpg [--center CL,CT,CW,CH] [--tol 10]
         -> compares the final Canva export with the mock in the two side
            strips (where the faces are). Mean pixel difference <= tol -> OK,
            i.e. Canva placed Joe / guest exactly where `crop` computed.
            Also writes <export>_check.jpg (export with the strips outlined)
            for the visual re-check. Exit code 2 on MISMATCH.

Times accept seconds (1314.5) or h:mm:ss / mm:ss. Needs ffmpeg + Pillow.
Run: py -3.14 -X utf8 E:\\Tool\\jre-thumb\\frames.py sheet clip.mp4 --start 0 --end 600
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLS, ROWS = 5, 4
CELL_W = 480


def parse_t(v):
    v = str(v).strip()
    if ":" not in v:
        return float(v)
    s = 0.0
    for part in v.split(":"):
        s = s * 60 + float(part)
    return s


def fmt(t):
    t = int(round(t))
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def duration(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(out.stdout.strip() or 0)


def font(size):
    for f in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def cmd_sheet(a):
    video = Path(a.video)
    start = parse_t(a.start)
    end = parse_t(a.end) if a.end is not None else duration(video)
    out = Path(a.out or video.with_suffix("").as_posix() + "_thumbframes")
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="jrethumb_"))
    try:
        # one decode pass, frames every `step` seconds starting at `start`
        subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{start}", "-t", f"{end - start}",
             "-i", str(video), "-vf", f"fps=1/{a.step},scale={CELL_W}:-2",
             "-q:v", "3", str(tmp / "f_%05d.jpg")], check=True)
        frames = sorted(tmp.glob("f_*.jpg"))
        if not frames:
            sys.exit("no frames extracted - check --start/--end")
        times = [start + i * a.step for i in range(len(frames))]
        per = COLS * ROWS
        f_big = font(30)
        index = []
        for si in range(0, len(frames), per):
            chunk = list(zip(frames[si:si + per], times[si:si + per]))
            w, h = Image.open(chunk[0][0]).size
            sheet = Image.new("RGB", (COLS * w, ROWS * h), "black")
            d = ImageDraw.Draw(sheet)
            for k, (fp, t) in enumerate(chunk):
                x, y = k % COLS * w, k // COLS * h
                sheet.paste(Image.open(fp), (x, y))
                label = f"{t:.1f}s  ({fmt(t)})"
                d.rectangle([x, y, x + 260, y + 40], fill="black")
                d.text((x + 8, y + 4), label, fill="yellow", font=f_big)
                d.rectangle([x, y, x + w - 1, y + h - 1], outline="#444")
            name = f"sheet_{si // per + 1:02d}.jpg"
            sheet.save(out / name, quality=85)
            index.append({"sheet": name, "times": [round(t, 2) for _, t in chunk]})
        (out / "index.json").write_text(json.dumps(
            {"video": str(video), "start": start, "end": end, "step": a.step,
             "sheets": index}, indent=1), encoding="utf-8")
        print(f"{len(frames)} frames -> {len(index)} sheets in {out}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_grab(a):
    video = Path(a.video)
    out = Path(a.out or video.with_suffix("").as_posix() + "_thumbframes")
    out.mkdir(parents=True, exist_ok=True)
    for tv in a.t:
        t = parse_t(tv)
        dst = out / f"frame_{t:.1f}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t}", "-i", str(video),
             "-frames:v", "1", str(dst)], check=True)
        im = Image.open(dst).convert("RGB")
        d = ImageDraw.Draw(im)
        f = font(22)
        for x in range(0, im.width, 100):
            d.line([(x, 0), (x, im.height)], fill=(0, 255, 255) if x % 500 else "red", width=1)
            d.text((x + 3, 3), str(x), fill="yellow", font=f)
        for y in range(0, im.height, 100):
            d.line([(0, y), (im.width, y)], fill=(0, 255, 255) if y % 500 else "red", width=1)
            d.text((3, y + 3), str(y), fill="yellow", font=f)
        im.save(dst.with_name(dst.stem + "_grid.jpg"), quality=85)
        print(dst)


# Element boxes (L, T, W, H) of the channel template DAHVNt9L56k on its 1920x1080 page.
TEMPLATE = {"left": (0.0, 0.0, 1120.9, 1080.0),
            "right": (950.6, -35.2, 969.4, 1141.5),
            "center": (638.3, 82.5, 624.7, 913.4)}
TEMPLATE_ID = "DAHVNt9L56k"
# The channel's 4K badge (user-supplied PNG, transparent). It is wider than the template's own badge
# (114x109 at 1772,29), so it sits in a 140x109 box with the same top and right edge.
LOGO_FILE = Path(__file__).with_name("logo_4k.png")
LOGO_BOX = (1746.1, 29.1, 140.0, 109.2)


def _csv(v, default):
    return tuple(float(x) for x in v.split(",")) if v else default


def _plan_put(plan_path, slot: str, img, box: dict, extra: dict | None = None) -> None:
    """Record one slot (image + element box + Canva imageBox) in the thumbnail plan."""
    p = Path(plan_path)
    plan = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"template": TEMPLATE_ID, "slots": {}}
    L0, T0, W0, H0 = LOGO_BOX
    plan["logo"] = {"img": str(LOGO_FILE), "element": {"left": L0, "top": T0, "width": W0, "height": H0},
                    "note": "replace the template's 4K badge (small element top-right, left≈1772) with this file, "
                            "then resize/position the element to this box"}
    L, T, W, H = TEMPLATE[slot]
    plan.setdefault("slots", {})[slot] = {"img": str(Path(img).resolve()),
                                          "element": {"left": L, "top": T, "width": W, "height": H},
                                          "image_box": box, **(extra or {})}
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"plan: {slot} -> {p}")


def cmd_crop(a):
    x1, y1, x2, y2 = (float(v) for v in a.head.split(","))
    L, T, W, H = _csv(a.panel, TEMPLATE[a.side])
    cl, ct, cw, ch = _csv(a.center, TEMPLATE["center"])
    if a.img:
        sw, sh = (float(v) for v in Image.open(a.img).size)
    else:
        sw, sh = (float(v) for v in a.src.lower().split("x"))
    # visible strip of this side panel, page x
    sx1, sx2 = (max(L, 0), cl) if a.side == "left" else (cl + cw, min(L + W, 1920))
    room = sx2 - sx1 - 2 * a.margin
    s = min(a.head_h / (y2 - y1), room / (x2 - x1))
    s = max(s, W / sw, H / sh)                    # image must still cover the panel
    iw, ih = sw * s, sh * s
    want_x = (sx1 + sx2) / 2 - (x1 + x2) / 2 * s  # page x of image left edge
    want_y = a.head_top - y1 * s
    left = min(0.0, max(W - iw, want_x - L))
    top = min(0.0, max(H - ih, want_y - T))
    px1, px2 = L + left + x1 * s, L + left + x2 * s
    py1, py2 = T + top + y1 * s, T + top + y2 * s
    gap = (cl - px2) if a.side == "left" else (px1 - (cl + cw))
    ok = gap >= 0 and px1 >= 0 and px2 <= 1920 and py1 >= 0
    box = {"left": round(left, 1), "top": round(top, 1), "width": round(iw, 1), "height": round(ih, 1)}
    check = (f"head on page x {px1:.0f}-{px2:.0f}, y {py1:.0f}-{py2:.0f} "
             f"(head {py2 - py1:.0f}px tall), gap to centre panel {gap:.0f}px -> "
             + ("OK" if ok else "OVERLAP / OFF-PAGE"))
    print(json.dumps(box))
    print("CHECK " + check)
    if a.plan and a.img and ok:
        _plan_put(a.plan, a.side, a.img, box, {"head": [x1, y1, x2, y2], "check": check})
    elif a.plan and not ok:
        print("plan NOT updated: fix the overlap first")
    sys.exit(0 if ok else 2)


def cmd_fill(a):
    """Centre (or any) slot: scale the image to cover the element, focus point (fraction of the image) centred."""
    L, T, W, H = TEMPLATE[a.slot]
    sw, sh = Image.open(a.img).size
    fx, fy = _csv(a.focus, (0.5, 0.5))
    s = max(W / sw, H / sh) * a.zoom
    iw, ih = sw * s, sh * s
    left = min(0.0, max(W - iw, W / 2 - fx * iw))
    top = min(0.0, max(H - ih, H / 2 - fy * ih))
    box = {"left": round(left, 1), "top": round(top, 1), "width": round(iw, 1), "height": round(ih, 1)}
    print(json.dumps(box))
    if a.plan:
        _plan_put(a.plan, a.slot, a.img, box)


def _layers_from_plan(plan_path) -> list[tuple]:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    out = []
    for slot in ("left", "right", "center"):          # bottom to top, as in the template
        s = plan["slots"].get(slot)
        if slot == "center" and (not s or not s.get("img")) and plan.get("center_ai_prompt"):
            continue                                  # AI centre: generated on Canva at approval, placeholder here
        if not s:
            sys.exit(f"plan has no '{slot}' slot yet")
        e, b = s["element"], s["image_box"]
        out.append((s["img"], e["left"], e["top"], e["width"], e["height"],
                    b["left"], b["top"], b["width"], b["height"]))
    return out


def cmd_mock(a):
    page = Image.new("RGB", (1920, 1080), "black")
    layers = _layers_from_plan(a.plan) if a.plan else []
    for spec in a.layer or []:
        src, *nums = spec.rsplit(",", 8)
        layers.append((src, *(float(v) for v in nums)))
    if not layers:
        sys.exit("give --plan or --layer")
    for src, L, T, W, H, bl, bt, bw, bh in layers:
        im = Image.open(src).convert("RGB").resize((round(bw), round(bh)))
        part = im.crop((round(-bl), round(-bt), round(-bl + W), round(-bt + H)))
        page.paste(part, (round(L), round(T)))
    cl, ct, cw, ch = _csv(a.frame, TEMPLATE["center"])
    d = ImageDraw.Draw(page)
    ai = json.loads(Path(a.plan).read_text(encoding="utf-8")).get("center_ai_prompt") if a.plan else None
    if ai and len(layers) == 2:
        import textwrap
        d.rectangle([cl, ct, cl + cw, ct + ch], fill="#2a2a2a")
        d.text((cl + 30, ct + 30), "AI (tạo trên Canva khi duyệt):", fill="#00bf63", font=font(30))
        d.multiline_text((cl + 30, ct + 80), textwrap.fill(ai, 38)[:900], fill="white", font=font(24), spacing=6)
    d.rectangle([cl, ct, cl + cw, ct + ch], outline="#00bf63", width=12)
    if a.logo:  # the channel's 4K badge, to see what it covers
        lx, ly, lw, lh = _csv(a.logo, LOGO_BOX)
        if LOGO_FILE.exists():
            logo = Image.open(LOGO_FILE).convert("RGBA").resize((round(lw), round(lh)), Image.LANCZOS)
            page.paste(logo, (round(lx), round(ly)), logo)
        else:
            d.rectangle([lx, ly, lx + lw, ly + lh], fill="#111111", outline="#d4a017", width=6)
            d.text((lx + 12, ly + 20), "4K", fill="white", font=font(54))
    page.save(a.out, quality=88)
    print(a.out)


def cmd_verify(a):
    from PIL import ImageChops, ImageStat
    ex = Image.open(a.export).convert("RGB").resize((1920, 1080))
    mk = Image.open(a.mock).convert("RGB").resize((1920, 1080))
    cl, ct, cw, ch = (float(v) for v in a.center.split(","))
    strips = {"left (Joe)": (0, 0, int(cl) - 8, 1080),
              "right (guest)": (int(cl + cw) + 8, 140, 1920, 1080)}  # skip 4K badge row
    bad = False
    for name, box in strips.items():
        diff = ImageChops.difference(ex.crop(box), mk.crop(box)).convert("L")
        m = ImageStat.Stat(diff).mean[0]
        ok = m <= a.tol
        bad |= not ok
        print(f"{name:14s} mean diff {m:5.1f} -> {'OK' if ok else 'MISMATCH'}")
    chk = ex.copy()
    d = ImageDraw.Draw(chk)
    for box in strips.values():
        d.rectangle(box, outline="yellow", width=4)
    out = Path(a.export).with_name(Path(a.export).stem + "_check.jpg")
    chk.save(out, quality=85)
    print(f"visual check image: {out}")
    sys.exit(2 if bad else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("video")
    s.add_argument("--start", default="0")
    s.add_argument("--end")
    s.add_argument("--step", type=float, default=1.5)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_sheet)
    g = sub.add_parser("grab")
    g.add_argument("video")
    g.add_argument("--t", action="append", required=True)
    g.add_argument("--out")
    g.set_defaults(fn=cmd_grab)
    c = sub.add_parser("crop")
    c.add_argument("--head", required=True, help="X1,Y1,X2,Y2 head box in source px (hair to chin, ear to ear)")
    c.add_argument("--panel", help="L,T,W,H of the side element (default: template DAHVNt9L56k)")
    c.add_argument("--center", help="CL,CT,CW,CH of the centre element (default: template)")
    c.add_argument("--side", choices=["left", "right"], required=True)
    c.add_argument("--img", help="the grabbed frame (its size is used; with --plan it is recorded)")
    c.add_argument("--plan", help="thumb_plan.json to record this slot in (only when CHECK is OK)")
    c.add_argument("--src", default="1920x1080")
    c.add_argument("--head-h", type=float, default=700, help="target head height on page")
    c.add_argument("--margin", type=float, default=15)
    c.add_argument("--head-top", type=float, default=40, help="page y of the top of the head")
    c.set_defaults(fn=cmd_crop)
    f = sub.add_parser("fill")
    f.add_argument("--img", required=True)
    f.add_argument("--slot", choices=["left", "right", "center"], default="center")
    f.add_argument("--focus", help="FX,FY point of the image to centre, as fractions 0-1 (default 0.5,0.5)")
    f.add_argument("--zoom", type=float, default=1.0, help=">1 zooms in past plain cover")
    f.add_argument("--plan")
    f.set_defaults(fn=cmd_fill)
    m = sub.add_parser("mock")
    m.add_argument("--plan", help="thumb_plan.json (left, right, center slots)")
    m.add_argument("--layer", action="append",
                   help="IMG,L,T,W,H,BL,BT,BW,BH (element box + imageBox), bottom to top")
    m.add_argument("--frame", help="CL,CT,CW,CH of the green centre frame (default: template)")
    m.add_argument("--logo", default=",".join(str(v) for v in LOGO_BOX),
                   help="L,T,W,H of the 4K badge, drawn from logo_4k.png ('' to skip)")
    m.add_argument("--out", required=True)
    m.set_defaults(fn=cmd_mock)
    v = sub.add_parser("verify")
    v.add_argument("--export", required=True)
    v.add_argument("--mock", required=True)
    v.add_argument("--center", default="638.3,82.5,624.7,913.4")
    v.add_argument("--tol", type=float, default=10)
    v.set_defaults(fn=cmd_verify)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
