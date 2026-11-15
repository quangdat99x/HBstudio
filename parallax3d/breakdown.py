"""Step 4 (optional): a short breakdown that shows the analysis, then cuts into the shot.

  original photo -> depth map wipes in -> the layers fly apart in 3D while the camera
  swings round the stack -> they close up again -> cross-fade into the cinematic render.

Each layer is drawn here as a flat card holding only its own depth band, so the gaps
between layers read clearly. Captions are Vietnamese (Segoe UI has the diacritics).

Usage: python breakdown.py <work_dir> <cinematic.mp4> <out.mp4>
"""
import math
import subprocess
import sys

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont

from render import FFMPEG, FPS, OUT_H, OUT_W, Scene, dev, ease

FONT_B = r"C:\Windows\Fonts\segoeuib.ttf"
FONT = r"C:\Windows\Fonts\segoeui.ttf"
PIVOT, GAP = 4.0, 0.42        # stack centre depth, spacing between cards when spread

# timeline (seconds)
T_DEPTH_IN, T_DEPTH_FULL, T_CARDS = 1.2, 2.8, 3.6
T_EXPLODE, T_HOLD, T_CLOSE, T_FADE, T_END = 4.0, 6.6, 7.6, 9.2, 9.8

CAPTIONS = [
    (1.4, 3.6, "PHÂN TÍCH ĐỘ SÂU", "Depth Anything V2  ·  sáng = gần, tối = xa"),
    (4.0, 7.4, "TÁCH LỚP THEO ĐỘ SÂU", "bầu trời · núi & thung lũng · đồi · lều · hai nhạc công · đá tiền cảnh"),
    (7.6, 9.4, "DỰNG KHÔNG GIAN 3D", "vá nền phía sau từng lớp  ·  camera điện ảnh"),
]


def phase(t, a, b):
    return min(max((t - a) / (b - a), 0.0), 1.0)


def look_at(C, target):
    z = target - C
    z = z / z.norm()
    x = torch.linalg.cross(z, torch.tensor([0.0, -1.0, 0.0], device=dev))
    x = x / x.norm()
    return torch.stack([x, torch.linalg.cross(z, x), z], 1)


class Breakdown:
    def __init__(self, work):
        self.s = Scene(work)
        s = self.s
        # cards far -> near: the sky, then one card per depth band holding the original
        # pixels of that band only (soft edges snapped to the image)
        disp = np.load(f"{work}/disp.npy")

        def step(c):
            x = np.clip((disp - (c - 0.012)) / 0.024, 0, 1)
            return x * x * (3 - 2 * x)
        plate_a = s.layers[0]["rgba"][0, 3].cpu().numpy()
        sky_a = 1 - plate_a if s.sky is not None else np.zeros_like(plate_a)
        bounds = [0.0] + list(s.cuts) + [None]
        bands = [sky_a] if s.sky is not None else []
        for lo, hi in zip(bounds[:-1], bounds[1:]):
            a = (step(lo) if lo > 0 else np.ones_like(disp)) - (step(hi) if hi is not None else 0)
            if lo == 0:
                a = a * plate_a
            bands.append(np.clip(a, 0, 1))
        photo_rgb = torch.from_numpy(cv2.cvtColor(cv2.imread(f"{work}/source.png"), cv2.COLOR_BGR2RGB)).to(dev).float().permute(2, 0, 1)[None] / 255
        cards = []
        for k, a in enumerate(bands):
            rgb = s.sky["rgba"][:, :3] if (s.sky is not None and k == 0) else photo_rgb
            cards.append(dict(rgb=rgb, a=torch.from_numpy(a.astype(np.float32)).to(dev)[None, None]))
        n = len(cards)
        for k, c in enumerate(cards):
            c["offset"] = ((n - 1) / 2 - k) * GAP          # far cards back, near cards forward
            col = cv2.applyColorMap(np.uint8([[int(255 * k / (n - 1))]]), cv2.COLORMAP_TURBO)[0, 0][::-1]
            c["color"] = tuple(int(v) for v in col)
        self.cards = cards
        src = cv2.cvtColor(cv2.imread(f"{work}/source.png"), cv2.COLOR_BGR2RGB)
        self.photo = torch.from_numpy(src).to(dev).float().permute(2, 0, 1)[None] / 255
        d8 = (np.load(f"{work}/depth.npy") * 255).astype(np.uint8)
        dep = cv2.cvtColor(cv2.applyColorMap(d8, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)
        self.depth = torch.from_numpy(dep).to(dev).float().permute(2, 0, 1)[None] / 255
        self.font_b = ImageFont.truetype(FONT_B, 44)
        self.font = ImageFont.truetype(FONT, 26)

    def plane(self, img, Z, C, Rm, f, zeros=True):
        """Card at depth Z, sized like the source frame seen at the pivot depth (so with
        every card at the pivot the stack matches the photo exactly)."""
        s = self.s
        d = torch.cat([s.pix / f, torch.ones_like(s.pix[..., :1])], -1) @ Rm.T
        lam = (Z - C[2]) / d[..., 2]
        P = C + lam[..., None] * d
        uv = P[..., :2] / PIVOT * s.fs + s.cs
        grid = (uv / torch.tensor([s.w, s.h], device=dev)) * 2 - 1
        out = F.grid_sample(img, grid[None], mode="bilinear", padding_mode="zeros" if zeros else "border", align_corners=False)
        return out * (lam > 0).float()[None, None], uv, lam

    def card_outline(self, Z, C, Rm, f):
        s = self.s
        pts = []
        for u, v in ((0, 0), (s.w, 0), (s.w, s.h), (0, s.h)):
            P = torch.tensor([(u - s.w / 2) / s.fs * PIVOT, (v - s.h / 2) / s.fs * PIVOT, Z], device=dev)
            pc = Rm.T @ (P - C)
            if pc[2] <= 0.05:
                return None
            pts.append((float(pc[0] / pc[2] * f + OUT_W / 2), float(pc[1] / pc[2] * f + OUT_H / 2)))
        return np.array(pts, np.int32)

    def frame(self, t):
        s = self.s
        # camera: slow push on the flat photo, then a swing round a pivot inside the stack
        e = ease(phase(t, T_EXPLODE, T_HOLD)) * (1 - ease(phase(t, T_CLOSE, T_FADE)))
        swing = math.sin(math.pi * 0.5 * e)
        # the base pose is the cinematic shot's first frame, so the closing cross-fade lines up
        C0, R0m, fc = s.camera(0.0)
        pivot = torch.tensor([0.0, (s.target[1] / s.target[2] * PIVOT).item(), PIVOT], device=dev)
        view = C0 + R0m[:, 2] * (pivot - C0).norm()
        theta, phi = math.radians(-34) * swing, math.radians(9) * swing
        off = (C0 - pivot) * (1 + 1.45 * swing)
        yaw = torch.tensor([[math.cos(theta), 0, math.sin(theta)], [0, 1, 0], [-math.sin(theta), 0, math.cos(theta)]], device=dev)
        pitch = torch.tensor([[1, 0, 0], [0, math.cos(phi), math.sin(phi)], [0, -math.sin(phi), math.cos(phi)]], device=dev)
        C = pivot + yaw @ pitch @ off
        Rm = look_at(C, view + (pivot + torch.tensor([0.25, 0.1, -0.5], device=dev) - view) * swing)
        f = fc * (0.98 + 0.02 * ease(phase(t, 0, T_CARDS)))

        if t < T_CARDS:
            photo, _, _ = self.plane(self.photo, PIVOT, C, Rm, f, zeros=False)
            depth, uv, _ = self.plane(self.depth, PIVOT, C, Rm, f, zeros=False)
            # depth wipes in left to right, then fades into the stack of cards
            edge = phase(t, T_DEPTH_IN, T_DEPTH_FULL) * (OUT_W + 200) - 100
            xs = s.pix[..., 0] + OUT_W / 2
            m = ((edge - xs) / 60).clamp(0, 1)[None, None]
            img = photo * (1 - m) + depth * m
            if t > T_DEPTH_FULL + 0.3:
                k = phase(t, T_DEPTH_FULL + 0.3, T_CARDS)
                img = img * (1 - k) + photo * k
            line = (1 - ((xs - edge).abs() / 2).clamp(0, 1))[None, None] * (0 < phase(t, T_DEPTH_IN, T_DEPTH_FULL) < 1)
            img = img * (1 - line) + line
            outlines = []
        else:
            img = torch.full((1, 3, OUT_H, OUT_W), 0.035, device=dev)
            outlines = []
            for c in self.cards:
                Z = PIVOT + c["offset"] * e
                rgb, _, _ = self.plane(c["rgb"], Z, C, Rm, f)
                a, _, _ = self.plane(c["a"], Z, C, Rm, f)
                img = rgb * (1 + 0.45 * e) * a + img * (1 - a)
                outlines.append((self.card_outline(Z, C, Rm, f), c["color"]))
        img = s.grade(img, t)
        arr = (img[0].permute(1, 2, 0).cpu().numpy() * 255 + 0.5).astype(np.uint8)
        if outlines and e > 0.02:
            over = arr.copy()
            for pts, col in outlines:
                if pts is not None:
                    cv2.polylines(over, [pts], True, col, 2, cv2.LINE_AA)
            arr = cv2.addWeighted(over, min(e * 1.5, 0.85), arr, 1 - min(e * 1.5, 0.85), 0)
        return self.caption(arr, t)

    def caption(self, arr, t):
        for a, b, title, sub in CAPTIONS:
            if a <= t <= b:
                k = min(phase(t, a, a + 0.35), 1 - phase(t, b - 0.35, b))
                im = Image.fromarray(arr)
                layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
                dr = ImageDraw.Draw(layer)
                x, y = 90, OUT_H - 170
                dr.rectangle([x - 24, y - 6, x - 18, y + 92], fill=(242, 170, 60, int(255 * k)))
                for dx, dy, col in ((2, 2, (0, 0, 0, int(160 * k))), (0, 0, (255, 255, 255, int(255 * k)))):
                    dr.text((x + dx, y + dy), title, font=self.font_b, fill=col)
                    dr.text((x + dx, y + 58 + dy), sub, font=self.font, fill=col[:3] + (int(col[3] * 0.85),))
                arr = np.array(Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB"))
        return arr


def main():
    work, cine, out = sys.argv[1], sys.argv[2], sys.argv[3]
    bd = Breakdown(work)
    cap = cv2.VideoCapture(cine)
    ok, first = cap.read()
    first = cv2.cvtColor(first, cv2.COLOR_BGR2RGB)
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
                             "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    torch.manual_seed(1)
    n = int(T_END * FPS)
    with torch.no_grad():
        for i in range(n):
            t = i / FPS
            arr = bd.frame(t)
            if t > T_FADE:
                k = phase(t, T_FADE, T_END)
                arr = (arr * (1 - k) + first * k + 0.5).astype(np.uint8)
            proc.stdin.write(arr.tobytes())
        # then the whole cinematic shot
        frame = first
        while ok:
            proc.stdin.write(frame.tobytes())
            ok, nxt = cap.read()
            if ok:
                frame = cv2.cvtColor(nxt, cv2.COLOR_BGR2RGB)
    proc.stdin.close()
    proc.wait()
    print("done", out)


if __name__ == "__main__":
    if len(sys.argv) > 4 and sys.argv[4] == "--stills":
        bd = Breakdown(sys.argv[1])
        with torch.no_grad():
            for t in (0.5, 2.2, 3.3, 5.0, 6.6, 8.2):
                cv2.imwrite(f"{sys.argv[1]}/_bd_{int(t * 10):03d}.png", cv2.cvtColor(bd.frame(t), cv2.COLOR_RGB2BGR))
        print("stills written")
    else:
        main()
