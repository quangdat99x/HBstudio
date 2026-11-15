"""Step 3: fly a 3D camera through the depth layers and encode an MP4.

Every layer is a heightfield seen from the source camera at the origin (pixel u,v with
disparity s sits at depth Z = 1 / (s*A + B), near = 1, sky = ZFAR). For each output
pixel the ray of the moving camera is intersected with the layer by fixed-point
iteration on the layer's depth, then colour and alpha are sampled there (backward
warping: no holes, bicubic filtering). Layers are blurred by their distance from the
focus plane (depth of field) and composited back to front.

Usage: python render.py <work_dir> <out.mp4> [--stills]
"""
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np
import torch
import torch.nn.functional as F

FFMPEG = r"E:\Tool\video-cutter-portable\ffmpeg\ffmpeg.exe"
OUT_W, OUT_H, FPS, SECONDS = 1920, 1080, 30, 10
ZFAR = 60.0
FOV_SRC = 1.1            # source focal length in image widths
OVERSCAN = 1.15          # output shows 1/OVERSCAN of the source width, room for the move
FRAME_CENTER = (768, 540)  # source pixel the shot is framed on
TARGET_DISP = 0.45       # the camera orbits a point at the musicians' depth
FOCUS_DISP = 0.45        # depth of field: in focus at the musicians
DOF = 4.0                # blur sigma (px) per unit of disparity away from focus
ITERS = 14
SKY_DRIFT = -26.0        # source px the clouds travel over the shot (negative = to the left)

# camera keyframes along the shot (t = 0 .. 1, eased): position in scene units (near
# ground = 1 unit away), zoom = extra focal length
CAM_FROM = dict(x=-0.03, y=0.012, z=-0.02, zoom=1.00)
CAM_TO = dict(x=0.03, y=-0.012, z=0.10, zoom=1.03)

dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def ease(t):
    return t * t * t * (t * (6 * t - 15) + 10)   # smootherstep


def gaussian_blur(x, sigma):
    if sigma < 0.3:
        return x
    r = int(math.ceil(sigma * 3))
    k = torch.exp(-torch.arange(-r, r + 1, device=dev, dtype=x.dtype) ** 2 / (2 * sigma * sigma))
    k = k / k.sum()
    c = x.shape[1]
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="replicate"), k.view(1, 1, 1, -1).repeat(c, 1, 1, 1), groups=c)
    x = F.conv2d(F.pad(x, (0, 0, r, r), mode="replicate"), k.view(1, 1, -1, 1).repeat(c, 1, 1, 1), groups=c)
    return x


class Scene:
    def __init__(self, work):
        meta = json.load(open(os.path.join(work, "layers.json"), encoding="utf-8"))
        self.w, self.h = meta["width"], meta["height"]
        self.cuts = meta["cuts"]
        self.layers = []
        for L in meta["layers"]:
            bgra = cv2.imread(os.path.join(work, L["name"] + ".png"), cv2.IMREAD_UNCHANGED)
            rgba = torch.from_numpy(cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)).to(dev).float() / 255
            disp = torch.from_numpy(np.load(os.path.join(work, L["name"] + "_disp.npy"))).to(dev).float()
            self.layers.append(dict(rgba=rgba.permute(2, 0, 1)[None], disp=disp[None, None], rep=L["disp"]))
        self.sky = None
        if meta.get("sky"):
            bgr = cv2.imread(os.path.join(work, meta["sky"]["file"]))
            rgb = torch.from_numpy(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).to(dev).float() / 255
            self.sky = dict(rgba=torch.cat([rgb.permute(2, 0, 1), torch.ones(1, self.h, self.w, device=dev)])[None],
                            disp=torch.zeros(1, 1, self.h, self.w, device=dev), rep=0.0, horizon=meta["sky"]["horizon"])
        self.B = 1.0 / ZFAR
        self.A = 1.0 - self.B
        self.fs = FOV_SRC * self.w
        self.cs = torch.tensor([self.w / 2, self.h / 2], device=dev)
        # look-at target: the framing centre pushed out to the musicians' depth
        zt = 1.0 / (TARGET_DISP * self.A + self.B)
        fx, fy = FRAME_CENTER
        self.target = torch.tensor([(fx - self.w / 2) / self.fs * zt, (fy - self.h / 2) / self.fs * zt, zt], device=dev)
        self.f_out = self.fs * OUT_W / (self.w / OVERSCAN)
        ys, xs = torch.meshgrid(torch.arange(OUT_H, device=dev, dtype=torch.float32) + 0.5,
                                torch.arange(OUT_W, device=dev, dtype=torch.float32) + 0.5, indexing="ij")
        self.pix = torch.stack([xs - OUT_W / 2, ys - OUT_H / 2], -1)   # (H, W, 2)

    def camera(self, t):
        e = ease(t)
        p = {k: CAM_FROM[k] + (CAM_TO[k] - CAM_FROM[k]) * e for k in CAM_FROM}
        C = torch.tensor([p["x"], p["y"], p["z"]], device=dev)
        z = self.target - C
        z = z / z.norm()
        up = torch.tensor([0.0, -1.0, 0.0], device=dev)
        x = torch.linalg.cross(z, up)
        x = x / x.norm()
        y = torch.linalg.cross(z, x)
        R = torch.stack([x, y, z], 1)          # camera -> world
        return C, R, self.f_out * p["zoom"]

    def warp(self, layer, C, R, f, drift=0.0):
        d_cam = torch.cat([self.pix / f, torch.ones_like(self.pix[..., :1])], -1)   # (H, W, 3)
        r = d_cam @ R.T
        s = torch.full(r.shape[:2], float(layer["rep"]), device=dev)
        for k in range(ITERS):
            Z = 1.0 / (s * self.A + self.B)
            lam = (Z - C[2]) / r[..., 2]
            P = C + lam[..., None] * r
            uv = P[..., :2] / P[..., 2:3] * self.fs + self.cs
            grid = (uv / torch.tensor([self.w, self.h], device=dev)) * 2 - 1
            sampled = F.grid_sample(layer["disp"], grid[None], mode="bilinear", padding_mode="border", align_corners=False)[0, 0]
            s = s + 0.6 * (sampled - s)
        if drift:
            # clouds travel sideways; the motion fades out towards the horizon
            hz = float(layer["horizon"])
            wgt = ((hz - uv[..., 1]) / 100).clamp(0, 1)
            shifted = uv.clone()
            shifted[..., 0] = uv[..., 0] - drift * wgt * wgt * (3 - 2 * wgt)
            grid = (shifted / torch.tensor([self.w, self.h], device=dev)) * 2 - 1
        rgba = F.grid_sample(layer["rgba"], grid[None], mode="bicubic", padding_mode="border", align_corners=False).clamp(0, 1)
        outside = (uv[..., 0] < 0) | (uv[..., 0] > self.w) | (uv[..., 1] < 0) | (uv[..., 1] > self.h)
        return rgba, outside

    def frame(self, t):
        C, R, f = self.camera(t)
        out = torch.zeros(1, 3, OUT_H, OUT_W, device=dev)
        worst = 0.0
        if self.sky is not None:
            rgba, _ = self.warp(self.sky, C, R, f, drift=SKY_DRIFT * ease(t))
            out = gaussian_blur(rgba[:, :3], DOF * FOCUS_DISP)
        for i, L in enumerate(self.layers):
            rgba, outside = self.warp(L, C, R, f)
            a = rgba[:, 3:4]
            if i == 0 and self.sky is None:
                a = torch.ones_like(a)
            prem = torch.cat([rgba[:, :3] * a, a], 1)
            prem = gaussian_blur(prem, DOF * abs(L["rep"] - FOCUS_DISP))
            out = prem[:, :3] + out * (1 - prem[:, 3:4])
            worst = max(worst, float((outside & (a[0, 0] > 0.05)).float().mean()))
        return self.grade(out, t), worst

    def grade(self, img, t):
        # bloom from the bright sunset sky
        lum = (img * torch.tensor([0.299, 0.587, 0.114], device=dev).view(1, 3, 1, 1)).sum(1, keepdim=True)
        bright = img * ((lum - 0.55).clamp(min=0) / 0.45)
        img = img + 0.35 * gaussian_blur(bright, 18) + 0.15 * gaussian_blur(bright, 60)
        # vignette
        yy, xx = self.pix[..., 1] / (OUT_H / 2), self.pix[..., 0] / (OUT_W / 2)
        rr = (xx * xx * 0.8 + yy * yy).clamp(max=2) / 1.8
        img = img * (1 - 0.22 * rr ** 1.6)
        # film grain, strongest in the mid-tones
        g = torch.randn(1, 1, OUT_H // 2, OUT_W // 2, device=dev)
        g = F.interpolate(g, size=(OUT_H, OUT_W), mode="bilinear", align_corners=False)
        img = img + g * 0.012 * (4 * lum * (1 - lum)).clamp(0, 1)
        return img.clamp(0, 1)


def to_u8(img):
    return (img[0].permute(1, 2, 0).cpu().numpy() * 255 + 0.5).astype(np.uint8)


def main():
    work, out = sys.argv[1], sys.argv[2]
    stills = "--stills" in sys.argv
    scene = Scene(work)
    n = FPS * SECONDS
    torch.manual_seed(0)
    if stills:
        for t in (0.0, 0.5, 1.0):
            img, worst = scene.frame(t)
            cv2.imwrite(os.path.join(work, f"_still_{int(t * 100):03d}.png"), cv2.cvtColor(to_u8(img), cv2.COLOR_RGB2BGR))
            print(f"t={t:.2f} outside-source share {worst:.4%}")
        return
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
                             "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    worst_all = 0.0
    with torch.no_grad():
        for i in range(n):
            img, worst = scene.frame(i / (n - 1))
            worst_all = max(worst_all, worst)
            proc.stdin.write(to_u8(img).tobytes())
            if i % 60 == 0:
                print(f"frame {i}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("done", out, f"max outside-source share {worst_all:.4%}")


if __name__ == "__main__":
    with torch.no_grad():
        main()
