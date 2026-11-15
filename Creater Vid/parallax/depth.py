"""Monocular depth of one image with Depth Anything V2 Large (Hugging Face, cached under
E:\\Tool\\bgremove\\hf). estimate(src, work) writes work/depth.npy (float32, 0..1, larger =
nearer) and depth.png. The model stays loaded between calls (batch renders)."""
import os

os.environ.setdefault("HF_HOME", r"E:\Tool\bgremove\hf")

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from scipy.ndimage import gaussian_filter

MODEL = "depth-anything/Depth-Anything-V2-Large-hf"
_model = None


def _load():
    global _model
    if _model is None:
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        proc = AutoImageProcessor.from_pretrained(MODEL)
        proc.keep_aspect_ratio = True
        proc.ensure_multiple_of = 14
        model = AutoModelForDepthEstimation.from_pretrained(
            MODEL, dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev).eval()
        _model = (proc, model)
    return _model


def _predict(img, short_side):
    proc, model = _load()
    inputs = proc(images=img, return_tensors="pt", size={"height": short_side, "width": short_side})
    with torch.no_grad():
        out = model(pixel_values=inputs["pixel_values"].to(model.device, model.dtype)).predicted_depth
    out = F.interpolate(out[:, None].float(), size=(img.height, img.width), mode="bicubic", align_corners=False)
    d = out[0, 0].cpu().numpy()
    return (d - d.min()) / (d.max() - d.min() + 1e-8)


def estimate(src, work):
    """Blend the native 518px pass (globally consistent) with a ~1024px pass (finer edges)."""
    img = Image.open(src).convert("RGB")
    coarse = _predict(img, 518)
    fine = _predict(img, min(1022, (min(img.size) // 14) * 14))
    base = gaussian_filter(coarse, 12)
    depth = np.clip(base + (coarse - base) * 0.3 + (fine - gaussian_filter(fine, 12)) * 0.7, 0, None)
    depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)
    np.save(os.path.join(work, "depth.npy"), depth.astype(np.float32))
    Image.fromarray((depth * 255).astype(np.uint8)).save(os.path.join(work, "depth.png"))
    return depth
