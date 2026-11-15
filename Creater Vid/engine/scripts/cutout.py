"""Background removal on this machine (free, instead of a paid background-removal API).

  "$BGREMOVE_PY" scripts/cutout.py assets/raw/watcher.png assets/raw/forge.png --out public/img
  "$BGREMOVE_PY" scripts/cutout.py assets/raw/fire_bowl.png --mode matting --out public/img

Modes (tested on The Watchers, 2026-09-30):
  general  BiRefNet 1024 (MIT). Same masks as the paid APIs (IoU 0.97-0.99), 0.2 s/image on the GPU. Default for
           characters, props, landscapes.
  matting  BiRefNet_HR-matting 2048: soft alpha, the only one that keeps flames and smoke translucent. Never for
           scenery (it made a rock landscape half transparent).
Always:
  - foreground colours re-estimated (pymatting), so soft edges do not keep the grey of the generation backdrop
    (paid API cut-outs showed a light grey outline around bodies on dark scenes);
  - rescue (general mode): BiRefNet drops thin detached parts such as a halo ring behind a head; anything clearly
    brighter or more colourful than the grey backdrop, detached from the body and away from the image border is
    added back (--no-rescue to skip).
Writes <out>/<name>.png (RGBA) and a proof sheet out/stills/cutouts.jpg (each cut-out on dark red and on grey):
look at it before using the cut-outs.
"""
import argparse, os, sys, time
from pathlib import Path

os.environ.setdefault("HF_HOME", os.environ.get("BGREMOVE_HF") or r"E:\Tool\bgremove\hf")
import numpy as np
import torch
from PIL import Image, ImageDraw
from pymatting import estimate_foreground_ml
from scipy import ndimage
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

MODELS = {"general": ("ZhengPeng7/BiRefNet", 1024), "matting": ("ZhengPeng7/BiRefNet_HR-matting", 2048)}


def load_model(mode):
    repo, size = MODELS[mode]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = AutoModelForImageSegmentation.from_pretrained(repo, trust_remote_code=True).to(dev).eval()
    if dev == "cuda":
        m = m.half()
    return m, size, dev


def predict(model, size, dev, img):
    norm = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    x = norm(transforms.ToTensor()(img.resize((size, size), Image.BICUBIC))).unsqueeze(0).to(dev)
    if dev == "cuda":
        x = x.half()
    with torch.no_grad():
        pred = model(x)[-1].sigmoid().float()
    return torch.nn.functional.interpolate(pred, size=(img.height, img.width), mode="bilinear")[0, 0].clamp(0, 1).cpu().numpy()


def rescue(raw, alpha, lo=22, hi=55, min_blob=150):
    """Add back detached parts brighter/more colourful than the backdrop that the model dropped (halos)."""
    rgb = raw.astype(np.float32)
    w = (alpha < 0.02).astype(np.float32)
    if w.mean() < 0.05:
        return alpha, 0.0
    s = max(rgb.shape[:2]) / 40
    den = ndimage.gaussian_filter(w, s, mode="nearest") + 1e-6
    bg = np.dstack([ndimage.gaussian_filter(rgb[..., c] * w, s, mode="nearest") / den for c in range(3)])
    d = np.linalg.norm(rgb - bg, axis=2)
    lumw = np.array([0.299, 0.587, 0.114], np.float32)
    lit = ((rgb @ lumw) > (bg @ lumw) + 8) | ((rgb.max(2) - rgb.min(2)) > (bg.max(2) - bg.min(2)) + 25)
    key = np.clip((d - lo) / (hi - lo), 0, 1) * lit
    cand = (key > 0.5) & (alpha < 0.5)
    lab, n = ndimage.label(cand)
    if n == 0:
        return alpha, 0.0
    sizes = ndimage.sum(cand, lab, range(1, n + 1))
    dist = ndimage.distance_transform_edt(alpha < 0.5)
    border = np.zeros_like(cand)
    border[:4, :] = border[-4:, :] = border[:, :4] = border[:, -4:] = True
    ok = [i for i in range(1, n + 1) if sizes[i - 1] >= min_blob and not ((lab == i) & border).any() and np.median(dist[lab == i]) >= 12]
    keep = ndimage.binary_dilation(np.isin(lab, ok), iterations=6)
    out = np.maximum(alpha, key * keep)
    return out, float((out - alpha).clip(0).sum() / alpha.size * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default="public/img")
    ap.add_argument("--mode", choices=list(MODELS), default="general")
    ap.add_argument("--no-rescue", action="store_true")
    ap.add_argument("--sheet", default="out/stills/cutouts.jpg")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    model, size, dev = load_model(a.mode)
    print(f"{a.mode}: {MODELS[a.mode][0]} on {dev}, loaded in {time.time() - t0:.1f}s", flush=True)
    done = []
    for p in a.images:
        img = Image.open(p).convert("RGB")
        raw = np.asarray(img)
        t = time.time()
        alpha = predict(model, size, dev, img)
        added = 0.0
        if a.mode == "general" and not a.no_rescue:
            alpha, added = rescue(raw, alpha)
        fg = estimate_foreground_ml(raw.astype(np.float64) / 255, alpha.astype(np.float64))
        dst = out / (Path(p).stem + ".png")
        Image.fromarray(np.dstack([np.clip(fg * 255 + 0.5, 0, 255), alpha * 255 + 0.5]).astype(np.uint8), "RGBA").save(dst)
        print(f"{dst}  {time.time() - t:.1f}s  foreground {float((alpha > 0.5).mean() * 100):.1f}%  rescued {added:.3f}%", flush=True)
        done.append(dst)
    # proof sheet: every cut-out on dark red and on mid grey (halos, grey fringes and holes show up here)
    th = 360
    rows = []
    for d in done:
        im = Image.open(d).convert("RGBA")
        im = im.resize((int(im.width * th / im.height), th))
        pair = Image.new("RGB", (im.width * 2 + 10, th + 24), (20, 20, 20))
        for k, col in enumerate([(70, 12, 8), (128, 128, 128)]):
            bg = Image.new("RGBA", im.size, col + (255,))
            bg.alpha_composite(im)
            pair.paste(bg.convert("RGB"), (k * (im.width + 10), 24))
        ImageDraw.Draw(pair).text((6, 4), d.name, fill=(255, 220, 120))
        rows.append(pair)
    if rows:
        W = max(r.width for r in rows)
        sheet = Image.new("RGB", (W, sum(r.height for r in rows)), (20, 20, 20))
        y = 0
        for r in rows:
            sheet.paste(r, (0, y))
            y += r.height
        Path(a.sheet).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(a.sheet, quality=88)
        print("proof sheet:", a.sheet)


if __name__ == "__main__":
    sys.exit(main())
