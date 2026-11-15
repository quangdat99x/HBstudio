"""Rescue what BiRefNet drops (thin halos, sparks, detached glowing parts) with a difference key against the
generation background, then re-estimate clean foreground colours.

The Higgsfield prompts ask for a flat grey backdrop, so the backdrop can be modelled from the pixels BiRefNet is sure
are background (normalised blur, follows gradients and vignetting). Pixels far from that backdrop, brighter or more
colourful than it (not shadows), in blobs big enough to not be noise, are added to the alpha.

  python bgrescue.py <method folder> [names...]   -> writes <method folder>_rescued/<name>.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from pymatting import estimate_foreground_ml
from scipy import ndimage

SRC = Path(r"K:\VideoLab\watchers-v2\assets\raw")
OUT = Path(r"K:\VideoLab\bgtest")
PAIRS = {"watcher": "watcher_a", "watcher_raised": "watcher_raised_n", "semjaza": "semjaza_n",
         "semjaza_raised": "semjaza_raised_n", "azazel_point": "azazel_point_n", "azazel_bound": "azazel_bound_n",
         "raphael": "raphael", "forge": "forge2", "humans": "humans", "hermon": "hermon_peak",
         "rocks": "rocks_fg", "feather": "feather"}

def blur(x, s):
    return ndimage.gaussian_filter(x, s, mode="nearest")

def rescue(raw, alpha, lo=22, hi=55, min_blob=150):
    rgb = raw.astype(np.float32)
    w = (alpha < 0.02).astype(np.float32)
    if w.mean() < 0.05:
        return alpha, 0.0
    s = max(rgb.shape[:2]) / 40
    den = blur(w, s) + 1e-6
    bg = np.dstack([blur(rgb[..., c] * w, s) / den for c in range(3)])
    d = np.linalg.norm(rgb - bg, axis=2)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    lum_bg = bg @ np.array([0.299, 0.587, 0.114], np.float32)
    chroma = rgb.max(2) - rgb.min(2)
    chroma_bg = bg.max(2) - bg.min(2)
    lit = (lum > lum_bg + 8) | (chroma > chroma_bg + 25)          # brighter or more colourful, not a shadow
    key = np.clip((d - lo) / (hi - lo), 0, 1) * lit
    cand = (key > 0.5) & (alpha < 0.5)
    lab, n = ndimage.label(cand)
    if n == 0:
        return alpha, 0.0
    sizes = ndimage.sum(cand, lab, range(1, n + 1))
    # only new, detached structures (a halo behind the head): not a rim around what the model already kept
    # (that re-adds grey edges and the grey inside translucent flames), not the backdrop's own border
    dist = ndimage.distance_transform_edt(alpha < 0.5)
    border = np.zeros_like(cand); border[:4, :] = border[-4:, :] = border[:, :4] = border[:, -4:] = True
    ok = []
    for i in range(1, n + 1):
        if sizes[i - 1] < min_blob: continue
        m = lab == i
        if (m & border).any() or np.median(dist[m]) < 12: continue
        ok.append(i)
    keep = np.isin(lab, ok)
    keep = ndimage.binary_dilation(keep, iterations=6)             # take the soft glow around a kept blob
    out = np.maximum(alpha, key * keep)
    return out, float((out - alpha).clip(0).sum() / alpha.size * 100)

if __name__ == "__main__":
    method = sys.argv[1]
    names = sys.argv[2:] or list(PAIRS)
    dst = OUT / f"{method}_rescued"
    dst.mkdir(exist_ok=True)
    for name in names:
        raw = np.asarray(Image.open(SRC / f"{PAIRS[name]}.png").convert("RGB"))
        alpha = np.asarray(Image.open(OUT / method / f"{name}.png"))[..., 3].astype(np.float32) / 255
        a2, added = rescue(raw, alpha)
        fg = estimate_foreground_ml(raw.astype(np.float64) / 255, a2.astype(np.float64))
        Image.fromarray(np.dstack([np.clip(fg * 255 + 0.5, 0, 255), a2 * 255 + 0.5]).astype(np.uint8), "RGBA").save(dst / f"{name}.png")
        print(f"{name:15s} rescued {added:5.3f}% of the frame")
