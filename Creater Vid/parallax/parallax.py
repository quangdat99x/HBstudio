"""Still image -> 3D camera clip (2.5D parallax), free, on this machine's GPU.

  one clip:   python parallax.py <image> --out clip.mp4 [--seconds 8] [--move orbit-right] ...
  many clips: python parallax.py --batch jobs.json   (the depth model loads once)
              jobs.json = [{"image": ..., "out": ..., "seconds": 8, "move": "push-in", ...}, ...]
  moves:      orbit-right orbit-left push-in pull-out truck-right truck-left crane-up crane-down drift

Steps: depth (Depth Anything V2 Large) -> layers cut at depth discontinuities, background
inpainted behind each -> camera flight -> MP4 (NVENC) + <out>_contact.jpg (first/middle/
last frame). Depth and layers are cached per image in <cache>/<name>_<hash>/ so another
move of the same image renders straight away. Paths are relative to the current folder.
Run with the bgremove Python (PyTorch + CUDA): "$BGREMOVE_PY" "$PARALLAX_PY" ...
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402

import depth as depth_mod  # noqa: E402
import layers as layers_mod  # noqa: E402
import render as render_mod  # noqa: E402

SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def prepare(image, cache_root):
    """Depth + layers for an image, cached by content hash."""
    with open(image, "rb") as fh:
        digest = hashlib.sha1(fh.read()).hexdigest()[:10]
    work = os.path.join(cache_root, f"{os.path.splitext(os.path.basename(image))[0]}_{digest}")
    if os.path.exists(os.path.join(work, "layers.json")):
        return work, True
    os.makedirs(work, exist_ok=True)
    img = cv2.imread(image, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"không đọc được ảnh {image}")
    cv2.imwrite(os.path.join(work, "source.png"), img)
    depth_mod.estimate(os.path.join(work, "source.png"), work)
    layers_mod.build(work)
    return work, False


def run_job(job, defaults):
    j = {**defaults, **{k: v for k, v in job.items() if v is not None}}
    t0 = time.time()
    if j["move"] not in render_mod.MOVES:
        raise ValueError(f"move không có: {j['move']} (có: {', '.join(render_mod.MOVES)})")
    w, h = SIZES.get(j["size"]) or tuple(int(x) for x in str(j["size"]).lower().split("x"))
    work, cached = prepare(j["image"], j["cache"])
    subject = None
    if j.get("subject"):
        subject = tuple(float(x) for x in str(j["subject"]).split(",")) if isinstance(j["subject"], str) else tuple(j["subject"])
    scene = render_mod.Scene(work, w, h, move=j["move"], strength=float(j["strength"]), subject=subject,
                             focus=j["focus"], dof=float(j["dof"]), sky_drift=float(j["sky_drift"]), look=j["look"])
    edge = scene.fit_overscan()
    frames = render_mod.render_clip(scene, j["out"], float(j["seconds"]), int(j["fps"]))
    info = {"out": j["out"], "image": j["image"], "move": j["move"], "seconds": float(j["seconds"]), "frames": frames,
            "size": f"{w}x{h}", "overscan": round(scene.overscan, 3), "subject_disp": round(scene.subject_disp, 3),
            "layers": len(scene.layers), "sky": scene.sky is not None, "edge_share": round(edge, 5),
            "cache": work, "cached": cached, "contact": os.path.splitext(j["out"])[0] + "_contact.jpg",
            "sec": round(time.time() - t0, 1)}
    print(json.dumps(info, ensure_ascii=False), flush=True)
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--batch", help="file JSON: danh sách job (mỗi job có image, out và tuỳ chọn như dưới)")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="16:9", help="16:9 | 9:16 | 1:1 | 4:5 | WxH")
    ap.add_argument("--move", default="orbit-right", help=" | ".join(render_mod.MOVES))
    ap.add_argument("--strength", type=float, default=1.0, help="biên độ chuyển động (0.5 nhẹ, 1 chuẩn, 1.5 mạnh)")
    ap.add_argument("--subject", help="tâm khung và điểm camera xoay quanh, phân số x,y của ảnh (vd 0.62,0.55); mặc định giữa ảnh")
    ap.add_argument("--focus", default="auto", help="auto (nét ở chủ thể) | none | độ sâu 0..1")
    ap.add_argument("--dof", type=float, default=4.0, help="độ nhòe ngoài vùng nét (0 = tắt)")
    ap.add_argument("--sky-drift", type=float, default=-20.0, help="mây trôi bao nhiêu px trong cả clip (0 = đứng yên)")
    ap.add_argument("--look", default="clean", help="clean (chỉ bloom) | film (thêm vignette, grain)")
    ap.add_argument("--cache", help="thư mục cache độ sâu/lớp (mặc định <thư mục out>/.parallax_cache)")
    a = ap.parse_args()

    if a.batch:
        jobs = json.load(open(a.batch, encoding="utf-8"))
    elif a.image and a.out:
        jobs = [{"image": a.image, "out": a.out}]
    else:
        ap.error("cần <image> --out <clip.mp4>, hoặc --batch jobs.json")
    defaults = {k: getattr(a, k) for k in ("seconds", "fps", "size", "move", "strength", "subject", "focus", "dof", "sky_drift", "look")}
    failed = 0
    for job in jobs:
        d = dict(defaults)
        d["cache"] = a.cache or os.path.join(os.path.dirname(os.path.abspath(job["out"])), ".parallax_cache")
        try:
            run_job(job, d)
        except Exception as e:  # noqa: BLE001  one bad image must not stop a batch
            failed += 1
            print(json.dumps({"out": job.get("out"), "error": str(e)}, ensure_ascii=False), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
