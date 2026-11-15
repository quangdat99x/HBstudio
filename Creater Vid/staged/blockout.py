"""3D blockout of a scene: the layout is decided in real 3D (metres) before any painting.

A scene JSON lists a camera and simple solids (boxes, ellipsoids, capsules, figures, a chain). The scene is
ray-marched as signed distance fields and written as:
  blockout.png   grey-shaded sketch (figures lighter, chain dark gold) -> the composition reference given to
                 the image model, so horizon, scale and contact with the ground are physically right
  depth.npy      distance along the camera axis per pixel (metres), sky = inf
  plates.png     plate index per pixel (0 sky, 1.. as listed in "plates") -> which layer each thing belongs to
  camera.json    focal length (px), pitch, position, plates, projected anchors (hands, chain points...)

Usage: python blockout.py scene.json <out_dir>
Units: metres, y up, camera looks toward -z before pitch. Objects carry "plate": the layer they belong to.
"""
import json
import math
import os
import sys

import cv2
import numpy as np


def rot_y(p, a):
    c, s = math.cos(a), math.sin(a)
    x, z = p[..., 0], p[..., 2]
    return np.stack([c * x + s * z, p[..., 1], -s * x + c * z], -1)


def sd_box(p, c, h, ry=0.0):
    q = rot_y(p - c, -ry)
    d = np.abs(q) - h
    return np.linalg.norm(np.maximum(d, 0), axis=-1) + np.minimum(np.max(d, -1), 0)


def sd_ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1) / np.maximum(k1, 1e-6)


def sd_capsule(p, a, b, r):
    pa, ba = p - a, b - a
    h = np.clip((pa * ba).sum(-1) / (ba * ba).sum(), 0, 1)
    return np.linalg.norm(pa - ba * h[..., None], axis=-1) - r


def rock_noise(p, amp):
    return amp * (np.sin(p[..., 0] * 3.1) * np.sin(p[..., 2] * 2.7) + 0.5 * np.sin(p[..., 1] * 5.3 + p[..., 0] * 1.7))


def figure_parts(o):
    """A human figure as capsules: standing, kneeling, raised_hand. Returns (sdf parts, anchors)."""
    x, y, z = o["pos"]
    h = o.get("height", 1.8)
    pose = o.get("pose", "standing")
    face = math.radians(o.get("face", 0))   # turn around y
    P = lambda dx, dy, dz: np.array([x + dx * math.cos(face) + dz * math.sin(face), y + dy, z - dx * math.sin(face) + dz * math.cos(face)])
    s = h / 1.8
    parts, anchors = [], {}
    if pose == "kneeling":
        parts += [("cap", P(0, 0.12 * s, 0.15 * s), P(0, 0.12 * s, -0.25 * s), 0.13 * s),          # shins on the ground
                  ("cap", P(0, 0.35 * s, 0), P(0, 0.95 * s, 0.08 * s), 0.24 * s),               # torso, bowed
                  ("sph", P(0, 1.1 * s, 0.2 * s), 0.12 * s),
                  ("cap", P(-0.22 * s, 0.9 * s, 0.05 * s), P(-0.08 * s, 0.45 * s, 0.32 * s), 0.07 * s),
                  ("cap", P(0.22 * s, 0.9 * s, 0.05 * s), P(0.08 * s, 0.45 * s, 0.32 * s), 0.07 * s)]
        anchors["wrists"] = P(0, 0.45 * s, 0.33 * s).tolist()
        anchors["head"] = P(0, 1.1 * s, 0.2 * s).tolist()
    else:
        parts += [("cap", P(0, 0.3 * s, 0), P(0, 1.45 * s, 0), 0.24 * s),                        # robed body
                  ("cap", P(0, 0.05 * s, 0), P(0, 0.5 * s, 0), 0.3 * s),                         # robe hem flare
                  ("sph", P(0, 1.68 * s, 0), 0.12 * s),
                  ("cap", P(0.27 * s, 1.4 * s, 0), P(0.3 * s, 0.85 * s, 0.1 * s), 0.065 * s)]
        if pose == "raised_hand":
            parts.append(("cap", P(-0.27 * s, 1.4 * s, 0), P(-0.36 * s, 1.95 * s, 0.05 * s), 0.065 * s))
            anchors["hand"] = P(-0.37 * s, 1.98 * s, 0.05 * s).tolist()
        else:
            parts.append(("cap", P(-0.27 * s, 1.4 * s, 0), P(-0.32 * s, 0.85 * s, 0.12 * s), 0.065 * s))
            anchors["hand"] = P(-0.32 * s, 0.84 * s, 0.13 * s).tolist()
        anchors["head"] = P(0, 1.68 * s, 0).tolist()
        anchors["feet"] = P(0, 0, 0).tolist()
    return parts, anchors


def scene_sdf(objs):
    """Build a list of (fn(p) -> distance, plate, shade class) and the figures' anchors."""
    items, anchors = [], {}
    for o in objs:
        t = o["type"]
        plate = o.get("plate", "mid")
        cls = o.get("class", "rock")
        if t == "box":
            c, h, ry, n = np.array(o["center"], float), np.array(o["half"], float), math.radians(o.get("rot_y", 0)), o.get("noise", 0.0)
            items.append((lambda p, c=c, h=h, ry=ry, n=n: sd_box(p, c, h, ry) + (rock_noise(p, n) if n else 0), plate, cls))
        elif t == "ellipsoid":
            c, r, n = np.array(o["center"], float), np.array(o["radii"], float), o.get("noise", 0.0)
            items.append((lambda p, c=c, r=r, n=n: sd_ellipsoid(p, c, r) + (rock_noise(p, n) if n else 0), plate, cls))
        elif t == "plane":
            yv = o["y"]
            items.append((lambda p, yv=yv: p[..., 1] - yv, plate, cls))
        elif t == "figure":
            parts, anc = figure_parts(o)
            anchors[o["id"]] = anc

            def fn(p, parts=parts):
                d = None
                for part in parts:
                    e = sd_capsule(p, part[1], part[2], part[3]) if part[0] == "cap" else np.linalg.norm(p - part[1], axis=-1) - part[2]
                    d = e if d is None else np.minimum(d, e)
                return d
            items.append((fn, plate, "figure"))
    return items, anchors


def catenary(a, b, sag, n=60):
    a, b = np.array(a, float), np.array(b, float)
    t = np.linspace(0, 1, n)[:, None]
    p = a + (b - a) * t
    p[:, 1] -= sag * 4 * t[:, 0] * (1 - t[:, 0])
    return p


def main():
    scene = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    W, H = scene.get("size", [1536, 1024])
    w, h = W // 2, H // 2                       # marched at half size, then upscaled
    cam = scene["camera"]
    pos = np.array(cam["pos"], float)
    pitch = math.radians(cam.get("pitch", 0))
    hfov = math.radians(cam.get("hfov", 65))
    f = (W / 2) / math.tan(hfov / 2)
    plates = scene["plates"]                    # far to near, without the sky
    items, anchors = scene_sdf(scene["objects"])

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (xs + 0.5) * 2 - W / 2
    dy = -((ys + 0.5) * 2 - H / 2)
    d = np.stack([dx / f, dy / f, -np.ones_like(dx)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    cp, sp = math.cos(pitch), math.sin(pitch)
    d = np.stack([d[..., 0], cp * d[..., 1] - sp * d[..., 2], sp * d[..., 1] + cp * d[..., 2]], -1)   # pitch around x
    fwd = np.array([0, -sp * -1 * 0 + math.sin(pitch), -math.cos(pitch)])
    fwd = np.array([0.0, math.sin(pitch), -math.cos(pitch)])

    t = np.zeros((h, w), np.float32)
    hit = np.full((h, w), -1, np.int32)
    alive = np.ones((h, w), bool)
    for _ in range(220):
        p = pos + d * t[..., None]
        ds = np.stack([fn(p) for fn, _, _ in items], 0)
        k = np.argmin(ds, 0)
        dist = np.take_along_axis(ds, k[None], 0)[0]
        done = alive & (dist < 0.002 * np.maximum(t, 1))
        hit[done] = k[done]
        alive &= ~done
        t = np.where(alive, t + np.maximum(dist, 0.004) * 0.9, t)
        alive &= t < 2000
        if not alive.any():
            break

    p = pos + d * t[..., None]
    z = (d * t[..., None] @ fwd)                 # distance along the camera axis
    z[hit < 0] = np.inf
    # normals by central differences on the hit item
    eps = 0.01
    nrm = np.zeros_like(p)
    for i, (fn, _, _) in enumerate(items):
        m = hit == i
        if not m.any():
            continue
        q = p[m]
        g = np.stack([fn(q + np.array(e)) - fn(q - np.array(e)) for e in ([eps, 0, 0], [0, eps, 0], [0, 0, eps])], -1)
        nrm[m] = g / np.maximum(np.linalg.norm(g, axis=-1, keepdims=True), 1e-6)
    light = np.array(scene.get("light", [-0.5, 0.7, 0.4]), float)
    light /= np.linalg.norm(light)
    lam = np.clip((nrm * light).sum(-1), 0, 1)
    base = {"rock": 0.42, "figure": 0.82, "far": 0.38}
    img = np.zeros((h, w), np.float32)
    for i, (_, _, cls) in enumerate(items):
        m = hit == i
        img[m] = base.get(cls, 0.45) * (0.35 + 0.65 * lam[m])
    fog = 1 - np.exp(-np.nan_to_num(z, posinf=4000) / scene.get("fog_m", 260))
    sky_col = np.array(scene.get("sky_rgb", [0.20, 0.24, 0.32]))
    rgb = img[..., None] * np.array([0.92, 0.9, 0.86]) * (1 - fog[..., None]) + sky_col * fog[..., None]
    rgb[hit < 0] = sky_col * (0.75 + 0.35 * (ys[hit < 0] / h))[..., None]
    plate_idx = np.zeros((h, w), np.uint8)
    for i, (_, plate, _) in enumerate(items):
        plate_idx[hit == i] = plates.index(plate) + 1

    def proj(pt):
        v = np.array(pt, float) - pos
        v = np.array([v[0], cp * v[1] + sp * v[2], -sp * v[1] + cp * v[2]])   # world -> camera (inverse pitch)
        return [float(W / 2 + f * v[0] / -v[2]), float(H / 2 - f * v[1] / -v[2]), float(-v[2])]

    big = cv2.resize((np.clip(rgb, 0, 1) * 255).astype(np.uint8)[..., ::-1], (W, H), interpolation=cv2.INTER_CUBIC)
    proj_anchors = {fid: {k: proj(v) for k, v in a.items()} for fid, a in anchors.items()}
    chains = []
    for c in scene.get("chains", []):
        a = anchors[c["from"][0]][c["from"][1]]
        b = anchors[c["to"][0]][c["to"][1]]
        pts = catenary(a, b, c.get("sag", 0.4))
        px = np.array([proj(q)[:2] for q in pts], np.int32)
        cv2.polylines(big, [px], False, (40, 95, 140), max(3, int(W / 320)), cv2.LINE_AA)
        chains.append({"from": c["from"], "to": c["to"], "px": px.tolist()})
    cv2.imwrite(os.path.join(out, "blockout.png"), big)
    np.save(os.path.join(out, "depth.npy"), cv2.resize(z.astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST))
    cv2.imwrite(os.path.join(out, "plates.png"), cv2.resize(plate_idx, (W, H), interpolation=cv2.INTER_NEAREST))
    info = {"size": [W, H], "f": f, "pitch_deg": cam.get("pitch", 0), "pos": cam["pos"], "plates": ["sky"] + plates,
            "anchors": proj_anchors, "chains": chains,
            "plate_depth": {pl: [float(np.nanmin(np.where(plate_idx == i + 1, z, np.inf))), float(np.nanmax(np.where(plate_idx == i + 1, z, -np.inf)))]
                            for i, pl in enumerate(plates)}}
    json.dump(info, open(os.path.join(out, "camera.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: info[k] for k in ("f", "plate_depth", "anchors")}, indent=1))


if __name__ == "__main__":
    main()
