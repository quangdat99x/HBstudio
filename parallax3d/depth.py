"""Step 1: monocular depth for one image with Depth Anything V2 Large.

Writes <work>/depth.npy (float32, larger = nearer, 0..1) and depth.png for a look.
Two passes are blended: the model's native 518px pass (globally consistent) and a
~1024px pass (finer edges on people, cloth, branches).
Usage: python depth.py <image> <work_dir>
"""
import os
import sys

os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bgremove", "hf"))   # <Tool>/bgremove/hf

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

MODEL = "depth-anything/Depth-Anything-V2-Large-hf"


def predict(model, processor, img, short_side):
    inputs = processor(images=img, return_tensors="pt",
                       size={"height": short_side, "width": short_side})
    with torch.no_grad():
        out = model(pixel_values=inputs["pixel_values"].to(model.device, model.dtype)).predicted_depth
    out = F.interpolate(out[:, None].float(), size=(img.height, img.width), mode="bicubic", align_corners=False)
    d = out[0, 0].cpu().numpy()
    return (d - d.min()) / (d.max() - d.min() + 1e-8)


def main():
    src, work = sys.argv[1], sys.argv[2]
    img = Image.open(src).convert("RGB")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoImageProcessor.from_pretrained(MODEL)
    processor.keep_aspect_ratio = True
    processor.ensure_multiple_of = 14
    model = AutoModelForDepthEstimation.from_pretrained(MODEL, torch_dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev).eval()

    coarse = predict(model, processor, img, 518)
    fine = predict(model, processor, img, 1022)
    # keep the coarse pass's large-scale ordering, take detail from the fine pass
    from scipy.ndimage import gaussian_filter
    detail = fine - gaussian_filter(fine, 12)
    depth = np.clip(gaussian_filter(coarse, 12) + (coarse - gaussian_filter(coarse, 12)) * 0.3 + detail * 0.7, 0, None)
    depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

    np.save(os.path.join(work, "depth.npy"), depth.astype(np.float32))
    Image.fromarray((depth * 255).astype(np.uint8)).save(os.path.join(work, "depth.png"))
    Image.fromarray((coarse * 255).astype(np.uint8)).save(os.path.join(work, "depth_coarse.png"))
    Image.fromarray((fine * 255).astype(np.uint8)).save(os.path.join(work, "depth_fine.png"))
    print("depth saved", depth.shape, "device", dev)


if __name__ == "__main__":
    main()
