"""Remove the painted flames from the forge image (keep the glowing blade), inpaint, re-cut with BiRefNet."""
import os
os.environ.setdefault("HF_HOME", r"E:\Tool\bgremove\hf")
import cv2, numpy as np, torch
from PIL import Image
from pymatting import estimate_foreground_ml
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

raw = np.asarray(Image.open(r"K:\VideoLab\watchers-v2\assets\raw\forge2.png").convert("RGB"))
H, W = raw.shape[:2]
r, g, b = [raw[..., i].astype(np.int16) for i in range(3)]
yy, xx = np.mgrid[0:H, 0:W]
# anvil: everything warmer than the grey backdrop above the blade, cut per column just above the blade,
# found as the yellowest row (the hot metal) between 23.5 % and 25 % of the height
y0, y1 = int(0.235 * H), int(0.25 * H)
blade_row = y0 + np.argmax(g[y0:y1], axis=0)
anvil = (xx > 0.30 * W) & (xx < 0.80 * W) & (yy < blade_row[None, :] - 3) & (r - b > 12) & (r > 140)
# brazier: flames over the dark stump are bright and warm; pale wisps over the backdrop are just warmer than grey
region = (yy > 0.45 * H) & (yy < 0.672 * H) & (xx > 0.57 * W) & (xx < 0.76 * W)
braz = region & (((r > 85) & (r - b > 45)) | ((r > 140) & (r - b > 12) & (g > 70)))
mask = (anvil | braz).astype(np.uint8)
# flames are translucent at the edges: grow the mask a little and fill small holes
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
out = cv2.inpaint(np.ascontiguousarray(raw[..., ::-1]), mask * 255, 9, cv2.INPAINT_TELEA)[..., ::-1]
# above the blade there is only backdrop: paint it grey instead of inpainting (that drags the blade's yellow up)
above = cv2.dilate(anvil.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & (yy < blade_row[None, :] - 1)
out = out.copy(); out[above] = raw[20, 20]
Image.fromarray(out).save(r"K:\VideoLab\watchers-v2\assets\raw\forge2_nofire.png")
Image.fromarray(mask * 255).save(r"K:\VideoLab\bgtest\forge_fire_mask.png")

model = AutoModelForImageSegmentation.from_pretrained("ZhengPeng7/BiRefNet", trust_remote_code=True).to("cuda").eval().half()
norm = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
x = norm(transforms.ToTensor()(Image.fromarray(out).resize((1024, 1024), Image.BICUBIC))).unsqueeze(0).to("cuda").half()
with torch.no_grad():
    pred = model(x)[-1].sigmoid().float()
alpha = torch.nn.functional.interpolate(pred, size=(H, W), mode="bilinear")[0, 0].clamp(0, 1).cpu().numpy()
fg = estimate_foreground_ml(out.astype(np.float64) / 255, alpha.astype(np.float64))
Image.fromarray(np.dstack([np.clip(fg * 255 + 0.5, 0, 255), alpha * 255 + 0.5]).astype(np.uint8), "RGBA").save(r"K:\VideoLab\watchers-v2\public\img\forge_nofire.png")
print("mask px", int(mask.sum()), "alpha fg %", round(float((alpha > 0.5).mean() * 100), 1))
