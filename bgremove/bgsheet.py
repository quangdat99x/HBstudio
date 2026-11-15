"""Comparison sheets for bgtest.py: every method composited on the film's own dark sky, full view + the two
regions where the methods disagree most, at 100 %. Writes K:\\VideoLab\\bgtest\\sheets\\<name>.jpg."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = Path(r"K:\VideoLab\watchers-v2")
OUT = Path(r"K:\VideoLab\bgtest")
SKY = {"watcher": "heaven_sky", "watcher_raised": "heaven_sky", "semjaza": "oath_sky", "semjaza_raised": "oath_sky",
       "azazel_point": "war_sky", "forge": "war_sky", "humans": "war_sky", "azazel_bound": "judgment_sky",
       "raphael": "judgment_sky", "rocks": "judgment_sky", "hermon": "hermon_sky", "feather": "judgment_sky"}
METHODS = [("hf", "Higgsfield (1 credit)"), ("birefnet", "BiRefNet 1024"), ("birefnet_hr", "BiRefNet_HR 2048"),
           ("birefnet_hr_matting", "BiRefNet_HR matting")]
metrics = json.loads((OUT / "metrics.json").read_text())
font = ImageFont.truetype("arial.ttf", 22)
small = ImageFont.truetype("arial.ttf", 17)
(OUT / "sheets").mkdir(exist_ok=True)

def rgba(method, name):
    p = SRC / "assets" / "cut" / f"{name}.png" if method == "hf" else OUT / method / f"{name}.png"
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32) / 255
    return a[..., :3], a[..., 3:]

for name, sky in SKY.items():
    layers = {m: rgba(m, name) for m, _ in METHODS}
    H, W = layers["hf"][1].shape[:2]
    bg = Image.open(SRC / "public" / "img" / f"{sky}.png").convert("RGB")
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * s + 1), int(bg.height * s + 1)), Image.LANCZOS)
    bg = np.asarray(bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))).astype(np.float32) / 255
    bg *= 0.8  # the plates sit a little darker in the film
    comp = {m: np.clip(fg * a + bg * (1 - a), 0, 1) for m, (fg, a) in layers.items()}
    # where do the methods disagree most? (360 px windows on a 90 px grid)
    alphas = np.stack([layers[m][1][..., 0] for m, _ in METHODS])
    dis = alphas.std(0)
    C = 360
    cells = []
    for y in range(0, H - C, 90):
        for x in range(0, W - C, 90):
            cells.append((dis[y:y + C, x:x + C].mean(), x, y))
    cells.sort(reverse=True)
    crops = []
    for score, x, y in cells:
        if all(abs(x - cx) > C or abs(y - cy) > C for _, cx, cy in crops): crops.append((score, x, y))
        if len(crops) == 2: break
    cw = 480
    fh = int(H * cw / W)
    sheet = Image.new("RGB", (cw * 4, 40 + fh + 2 * (C + 10) + 10), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for i, (m, label) in enumerate(METHODS):
        im = Image.fromarray((comp[m] * 255 + 0.5).astype(np.uint8))
        sheet.paste(im.resize((cw, fh), Image.LANCZOS), (i * cw, 40))
        mm = metrics[name].get(m, {})
        info = label if m == "hf" else f"{label}  IoU {mm.get('iou_vs_hf', 0):.3f}"
        d.text((i * cw + 8, 8), info, fill=(255, 220, 120), font=font)
        for j, (_, x, y) in enumerate(crops):
            crop = im.crop((x, y, x + C, y + C))
            sheet.paste(crop, (i * cw + (cw - C) // 2, 40 + fh + 10 + j * (C + 10)))
            if i == 0:
                sx, sy = x * cw / W, 40 + y * cw / W
                for k in range(4):
                    d.rectangle([k * cw + sx, sy, k * cw + sx + C * cw / W, sy + C * cw / W], outline=(255, 80, 80), width=2)
    d.text((8, sheet.height - 26), f"{name}: 2 vùng khác nhau nhiều nhất (khung đỏ), 100%", fill=(170, 170, 170), font=small)
    sheet.save(OUT / "sheets" / f"{name}.jpg", quality=90)
    print(name, [(round(float(sc), 3), x, y) for sc, x, y in crops])
