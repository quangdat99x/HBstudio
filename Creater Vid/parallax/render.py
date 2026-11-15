"""Fly a 3D camera through the depth layers of one image and encode an MP4.

Every layer is a heightfield seen from the source camera at the origin (pixel u,v with
disparity s sits at depth Z = 1 / (s*A + B), near = 1 unit, sky = ZFAR). For each output
pixel the ray of the moving camera is intersected with the layer by fixed-point iteration
on the layer's depth, then colour and alpha are sampled there (backward warping: no holes,
bicubic filtering). Layers are blurred by their distance from the focus plane and
composited back to front. The sky layer can drift (clouds).
"""
import json
import math
import os
import shutil
import subprocess

import cv2
import numpy as np
import torch
import torch.nn.functional as F

_TOOL_FFMPEG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "video-cutter-portable", "ffmpeg", "ffmpeg.exe")   # <Tool>/video-cutter-portable/ffmpeg
FFMPEG = shutil.which("ffmpeg") or _TOOL_FFMPEG
if os.path.exists(_TOOL_FFMPEG):
    FFMPEG = _TOOL_FFMPEG   # this build has NVENC
ZFAR = 60.0
FOV_SRC = 1.1            # source focal length in image widths
ITERS = 14
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Camera moves, in scene units (the nearest ground is 1 unit away); `a` = 0.03 * strength.
# look: the camera keeps the subject at the same place on screen (orbit); without it the
# camera only translates (truck). zoom = extra focal length at the end.
MOVES = {
    "orbit-right": lambda a: dict(frm=(-a, 0.4 * a, -0.02), to=(a, -0.4 * a, 0.10), zoom=1.03, look=True),
    "orbit-left":  lambda a: dict(frm=(a, 0.4 * a, -0.02), to=(-a, -0.4 * a, 0.10), zoom=1.03, look=True),
    "push-in":     lambda a: dict(frm=(0, 0.2 * a, -0.03), to=(0, -0.2 * a, 0.17 * a / 0.03), zoom=1.04, look=True),
    "pull-out":    lambda a: dict(frm=(0, -0.2 * a, 0.17 * a / 0.03), to=(0, 0.2 * a, -0.03), zoom=0.96, look=True),
    "truck-right": lambda a: dict(frm=(-1.3 * a, 0, 0.03), to=(1.3 * a, 0, 0.03), zoom=1.0, look=False),
    "truck-left":  lambda a: dict(frm=(1.3 * a, 0, 0.03), to=(-1.3 * a, 0, 0.03), zoom=1.0, look=False),
    "crane-up":    lambda a: dict(frm=(0, 1.1 * a, 0.0), to=(0, -1.1 * a, 0.06), zoom=1.02, look=True),
    "crane-down":  lambda a: dict(frm=(0, -1.1 * a, 0.06), to=(0, 1.1 * a, 0.0), zoom=1.0, look=True),
    "drift":       lambda a: dict(frm=(-0.3 * a, 0, 0.0), to=(0.3 * a, 0, 0.05), zoom=1.01, look=True),
}


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
    def __init__(self, work, out_w=1920, out_h=1080, move="orbit-right", strength=1.0, subject=None,
                 focus="auto", dof=4.0, sky_drift=-20.0, look="clean", overscan=1.12):
        meta = json.load(open(os.path.join(work, "layers.json"), encoding="utf-8"))
        self.w, self.h = meta["width"], meta["height"]
        self.cuts = meta["cuts"]
        self.out_w, self.out_h = out_w, out_h
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

        # subject: where the shot is framed and what the camera orbits / focuses on
        disp = np.load(os.path.join(work, "disp.npy"))
        if subject:
            sx, sy = subject
            bx = (slice(int(max(0, sy - 0.1) * self.h), int(min(1, sy + 0.1) * self.h) + 1),
                  slice(int(max(0, sx - 0.08) * self.w), int(min(1, sx + 0.08) * self.w) + 1))
            self.subject_disp = float(np.percentile(disp[bx], 75))
        else:
            sx, sy = 0.5, 0.5
            self.subject_disp = float(np.percentile(disp[int(0.3 * self.h):int(0.85 * self.h), int(0.25 * self.w):int(0.75 * self.w)], 70))
        self.subject_disp = max(self.subject_disp, 0.05)
        self.focus_disp = self.subject_disp if focus in (None, "auto") else (None if focus == "none" else float(focus))
        self.dof = dof
        self.sky_drift = sky_drift
        self.look_mode = look
        self.frame_frac = (sx, sy)
        p = MOVES[move](0.03 * strength)
        self.cam_from, self.cam_to, self.zoom_to, self.look = p["frm"], p["to"], p["zoom"], p["look"]
        self.set_overscan(overscan)
        ys, xs = torch.meshgrid(torch.arange(out_h, device=dev, dtype=torch.float32) + 0.5,
                                torch.arange(out_w, device=dev, dtype=torch.float32) + 0.5, indexing="ij")
        self.pix = torch.stack([xs - out_w / 2, ys - out_h / 2], -1)
        # the ray/heightfield search runs on a half-size grid (the warp is smooth inside a
        # layer), warm-started from the previous frame; colour is sampled at full size
        hh, hw = out_h // 2, out_w // 2
        ys, xs = torch.meshgrid((torch.arange(hh, device=dev, dtype=torch.float32) + 0.5) * out_h / hh,
                                (torch.arange(hw, device=dev, dtype=torch.float32) + 0.5) * out_w / hw, indexing="ij")
        self.pix_half = torch.stack([xs - out_w / 2, ys - out_h / 2], -1)
        self.warm = {}

    def set_overscan(self, overscan):
        self.overscan = overscan
        # visible source width so the output aspect fits inside the source, then the margin
        vis_w = min(self.w, self.h * self.out_w / self.out_h) / overscan
        vis_h = vis_w * self.out_h / self.out_w
        fx = min(max(self.frame_frac[0] * self.w, vis_w / 2), self.w - vis_w / 2)
        fy = min(max(self.frame_frac[1] * self.h, vis_h / 2), self.h - vis_h / 2)
        zt = 1.0 / (self.subject_disp * self.A + self.B)
        self.target = torch.tensor([(fx - self.w / 2) / self.fs * zt, (fy - self.h / 2) / self.fs * zt, zt], device=dev)
        self.f_out = self.fs * self.out_w / vis_w

    def camera(self, t):
        e = ease(float(t))
        C = torch.tensor([a + (b - a) * e for a, b in zip(self.cam_from, self.cam_to)], device=dev)
        target = self.target if self.look else self.target + C
        z = target - C
        z = z / z.norm()
        x = torch.linalg.cross(z, torch.tensor([0.0, -1.0, 0.0], device=dev))
        x = x / x.norm()
        y = torch.linalg.cross(z, x)
        return C, torch.stack([x, y, z], 1), self.f_out * (1 + (self.zoom_to - 1) * e)

    def warp(self, layer, C, R, f, drift=0.0):
        r = torch.cat([self.pix_half / f, torch.ones_like(self.pix_half[..., :1])], -1) @ R.T
        size = torch.tensor([self.w, self.h], device=dev)
        key = id(layer)
        if layer is self.sky:
            iters, s = 1, torch.zeros(r.shape[:2], device=dev)
        elif key in self.warm:
            iters, s = 5, self.warm[key]
        else:
            iters, s = ITERS, torch.full(r.shape[:2], float(layer["rep"]), device=dev)
        for _ in range(iters):
            Z = 1.0 / (s * self.A + self.B)
            lam = (Z - C[2]) / r[..., 2]
            P = C + lam[..., None] * r
            uv = P[..., :2] / P[..., 2:3] * self.fs + self.cs
            sampled = F.grid_sample(layer["disp"], ((uv / size) * 2 - 1)[None], mode="bilinear",
                                    padding_mode="border", align_corners=False)[0, 0]
            s = s + 0.6 * (sampled - s)
        self.warm[key] = s
        uv = F.interpolate(uv.permute(2, 0, 1)[None], size=(self.out_h, self.out_w), mode="bilinear",
                           align_corners=False)[0].permute(1, 2, 0)
        grid = (uv / size) * 2 - 1
        if drift:
            hz = float(layer["horizon"])
            wgt = ((hz - uv[..., 1]) / 100).clamp(0, 1)
            shifted = uv.clone()
            shifted[..., 0] = uv[..., 0] - drift * wgt * wgt * (3 - 2 * wgt)
            grid = (shifted / size) * 2 - 1
        rgba = F.grid_sample(layer["rgba"], grid[None], mode="bicubic", padding_mode="border", align_corners=False).clamp(0, 1)
        outside = (uv[..., 0] < 0) | (uv[..., 0] > self.w) | (uv[..., 1] < 0) | (uv[..., 1] > self.h)
        return rgba, outside

    def blur_for(self, rep):
        return 0.0 if self.focus_disp is None else self.dof * abs(rep - self.focus_disp)

    def frame(self, t, grade=True, check=False):
        t = float(t)
        C, R, f = self.camera(t)
        out = torch.zeros(1, 3, self.out_h, self.out_w, device=dev)
        worst = 0.0
        if self.sky is not None:
            rgba, _ = self.warp(self.sky, C, R, f, drift=self.sky_drift * ease(t))
            out = gaussian_blur(rgba[:, :3], self.blur_for(0.0))
        for i, L in enumerate(self.layers):
            rgba, outside = self.warp(L, C, R, f)
            a = rgba[:, 3:4]
            if i == 0 and self.sky is None:
                a = torch.ones_like(a)
            prem = gaussian_blur(torch.cat([rgba[:, :3] * a, a], 1), self.blur_for(L["rep"]))
            out = prem[:, :3] + out * (1 - prem[:, 3:4])
            if check:
                worst = max(worst, float((outside & (a[0, 0] > 0.05)).float().mean()))
        return (self.grade(out) if grade else out.clamp(0, 1)), worst

    def grade(self, img):
        """clean: bloom only (the film adds its own grade) · film: bloom, vignette, grain."""
        lum = (img * torch.tensor([0.299, 0.587, 0.114], device=dev).view(1, 3, 1, 1)).sum(1, keepdim=True)
        bright = F.avg_pool2d(img * ((lum - 0.55).clamp(min=0) / 0.45), 4)        # bloom at quarter size
        glow = 0.3 * gaussian_blur(bright, 4.5) + 0.12 * gaussian_blur(bright, 15)
        img = img + F.interpolate(glow, size=img.shape[-2:], mode="bilinear", align_corners=False)
        if self.look_mode == "film":
            yy, xx = self.pix[..., 1] / (self.out_h / 2), self.pix[..., 0] / (self.out_w / 2)
            rr = (xx * xx * 0.8 + yy * yy).clamp(max=2) / 1.8
            img = img * (1 - 0.22 * rr ** 1.6)
            g = F.interpolate(torch.randn(1, 1, self.out_h // 2, self.out_w // 2, device=dev),
                              size=(self.out_h, self.out_w), mode="bilinear", align_corners=False)
            img = img + g * 0.012 * (4 * lum * (1 - lum)).clamp(0, 1)
        return img.clamp(0, 1)

    def fit_overscan(self, limit=1.45):
        """Widen the margin until no frame of the move samples beyond the source edges."""
        while True:
            self.warm = {}
            worst = max(self.frame(t, grade=False, check=True)[1] for t in np.linspace(0, 1, 7))
            if worst <= 0.0002 or self.overscan >= limit:
                self.warm = {}
                return worst
            self.set_overscan(self.overscan + 0.03)


def to_u8(img):
    return (img[0].permute(1, 2, 0) * 255 + 0.5).clamp(0, 255).to(torch.uint8).cpu().numpy()


def encoder_args():
    probe = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "h264_nvenc" in probe:
        return ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "16", "-b:v", "0",
                "-spatial-aq", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"]


def render_clip(scene, out, seconds, fps=30, contact=True):
    n = max(2, int(round(seconds * fps)))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{scene.out_w}x{scene.out_h}", "-r", str(fps), "-i", "-", *encoder_args(),
                             "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    keep = {0: None, n // 2: None, n - 1: None}
    torch.manual_seed(0)
    with torch.no_grad():
        for i in range(n):
            img, _ = scene.frame(i / (n - 1))
            arr = to_u8(img)
            proc.stdin.write(arr.tobytes())
            if i in keep:
                keep[i] = arr
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed for " + out)
    if contact:
        w = 640
        h = int(w * scene.out_h / scene.out_w)
        sheet = np.hstack([cv2.resize(keep[k], (w, h), interpolation=cv2.INTER_AREA) for k in sorted(keep)])
        cv2.imwrite(os.path.splitext(out)[0] + "_contact.jpg", cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 88])
    return n
