"""Local background removal test against the Higgsfield remover, on the Watchers v2 images.

  E:\\Tool\\bgremove\\.venv\\Scripts\\python.exe E:\\Tool\\bgremove\\bgtest.py

For every image and model: alpha from BiRefNet (MIT licence, runs on the GPU), foreground colours decontaminated
with pymatting (removes the grey of the generation background from soft edges), timings, and agreement with the
Higgsfield cutout. Writes K:\\VideoLab\\bgtest\\<model>\\<name>.png and metrics.json.
"""
import json, os, sys, time
from pathlib import Path

os.environ.setdefault("HF_HOME", r"E:\Tool\bgremove\hf")
import numpy as np
import torch
from PIL import Image
from pymatting import estimate_foreground_ml
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

SRC = Path(r"K:\VideoLab\watchers-v2\assets")
OUT = Path(r"K:\VideoLab\bgtest")
PAIRS = {  # HF cutout -> raw image it was cut from
    "watcher": "watcher_a", "watcher_raised": "watcher_raised_n", "semjaza": "semjaza_n",
    "semjaza_raised": "semjaza_raised_n", "azazel_point": "azazel_point_n", "azazel_bound": "azazel_bound_n",
    "raphael": "raphael", "forge": "forge2", "humans": "humans", "hermon": "hermon_peak",
    "rocks": "rocks_fg", "feather": "feather",
}
MODELS = {  # name -> (repo, square input size)
    "birefnet": ("ZhengPeng7/BiRefNet", 1024),
    "birefnet_hr": ("ZhengPeng7/BiRefNet_HR", 2048),
    "birefnet_hr_matting": ("ZhengPeng7/BiRefNet_HR-matting", 2048),
}
only = sys.argv[1:]

torch.set_float32_matmul_precision("high")
norm = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])

def load_rgb(name):
    return Image.open(SRC / "raw" / f"{name}.png").convert("RGB")

metrics = json.loads((OUT / "metrics.json").read_text()) if (OUT / "metrics.json").exists() else {}
for mname, (repo, size) in MODELS.items():
    if only and mname not in only: continue
    t0 = time.time()
    model = AutoModelForImageSegmentation.from_pretrained(repo, trust_remote_code=True).to("cuda").eval().half()
    print(f"{mname}: loaded in {time.time() - t0:.1f}s, VRAM {torch.cuda.memory_allocated() / 2**30:.2f} GB", flush=True)
    (OUT / mname).mkdir(parents=True, exist_ok=True)
    for cut, raw in PAIRS.items():
        img = load_rgb(raw)
        W, H = img.size
        x = norm(transforms.ToTensor()(img.resize((size, size), Image.BICUBIC))).unsqueeze(0).to("cuda").half()
        torch.cuda.synchronize(); t = time.time()
        with torch.no_grad():
            pred = model(x)[-1].sigmoid().float()
        torch.cuda.synchronize(); t_inf = time.time() - t
        alpha = torch.nn.functional.interpolate(pred, size=(H, W), mode="bilinear", align_corners=False)[0, 0].clamp(0, 1).cpu().numpy()
        rgb = np.asarray(img).astype(np.float64) / 255
        t = time.time()
        fg = estimate_foreground_ml(rgb, alpha.astype(np.float64))
        t_fg = time.time() - t
        out = np.dstack([np.clip(fg * 255 + 0.5, 0, 255), alpha * 255 + 0.5]).astype(np.uint8)
        Image.fromarray(out, "RGBA").save(OUT / mname / f"{cut}.png")
        # agreement with the Higgsfield cutout
        hf = np.asarray(Image.open(SRC / "cut" / f"{cut}.png"))[..., 3].astype(np.float32) / 255
        a, b = alpha > 0.5, hf > 0.5
        iou = (a & b).sum() / max(1, (a | b).sum())
        m = metrics.setdefault(cut, {})
        m[mname] = dict(infer_s=round(t_inf, 3), fg_s=round(t_fg, 2), iou_vs_hf=round(float(iou), 4),
                        mad_vs_hf=round(float(np.abs(alpha - hf).mean()), 4),
                        soft_pct=round(float(((alpha > 0.02) & (alpha < 0.98)).mean() * 100), 2),
                        only_local_pct=round(float((a & ~b).mean() * 100), 2), only_hf_pct=round(float((b & ~a).mean() * 100), 2))
        print(f"  {cut:15s} infer {t_inf:5.2f}s  fg {t_fg:5.1f}s  IoU {iou:.4f}  soft {m[mname]['soft_pct']:5.2f}%  "
              f"+local {m[mname]['only_local_pct']:4.2f}%  +hf {m[mname]['only_hf_pct']:4.2f}%", flush=True)
    del model; torch.cuda.empty_cache()
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=1))
print("done")
