"""Step 2: split the image into depth layers ready for a 3D camera.

Each layer is a heightfield (colour + its own depth + alpha), not a flat card, so a
continuous surface (the ground) can cross a layer boundary without tearing. Layer
boundaries are put at depth discontinuities (occlusion edges); behind every layer the
colour and depth that the nearer layers hide are inpainted, so a camera move reveals
background instead of holes.

build(work) needs source.png and depth.npy (depth.py) in the work folder and writes
layer_XX.png (RGBA), layer_XX_disp.npy, sky.png, disp.npy, layers.json and _layers_sheet.png.
"""
import json
import os
import sys

import cv2
import numpy as np

MAX_LAYERS = 7          # cuts, the back plate comes on top of this
EDGE_JUMP = 0.06        # disparity jump inside a 7px window that counts as an occlusion edge
MIN_SPACING = 0.05      # between two cuts
HALO = 1                # px removed around nearer objects before inpainting a layer
REVEAL = 90             # px behind an occlusion edge that a camera move can uncover


def guided_filter(guide, src, r, eps):
    mean = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1))
    mg, ms = mean(guide), mean(src)
    a = (mean(guide * src) - mg * ms) / (mean(guide * guide) - mg * mg + eps)
    b = ms - a * mg
    return mean(a) * guide + mean(b)


def choose_cuts(disp):
    k = np.ones((7, 7), np.uint8)
    near, far = cv2.dilate(disp, k), cv2.erode(disp, k)
    edge = (near - far) > EDGE_JUMP
    f, n = far[edge], near[edge]
    margin = 0.2 * (n - f)
    lo, hi = f + margin, n - margin
    grid = np.arange(0.02, 0.98, 0.005)
    alive = np.ones(len(f), bool)
    cuts = []
    for _ in range(MAX_LAYERS):
        score = np.array([np.count_nonzero(alive & (lo < c) & (c < hi)) for c in grid])
        for c in cuts:
            score[np.abs(grid - c) < MIN_SPACING] = 0
        best = int(score.argmax())
        if score[best] < 0.004 * len(f):
            break
        c = float(grid[best])
        cuts.append(c)
        alive &= ~((lo < c) & (c < hi))
    return sorted(cuts), edge


def inpaint(img, hole, radius=6):
    """Telea at half size for the structure (holes can be a quarter of the frame)."""
    h, w = hole.shape
    small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    hs = cv2.resize(hole.astype(np.uint8), (w // 2, h // 2), interpolation=cv2.INTER_NEAREST)
    filled = cv2.inpaint(small, hs, radius, cv2.INPAINT_TELEA)
    filled = cv2.resize(filled, (w, h), interpolation=cv2.INTER_CUBIC)
    out = img.copy()
    out[hole] = filled[hole]
    return out


def mirror_fill(img, hole):
    """Texture for a hole: each hole pixel copies the known pixel mirrored across its
    nearest hole edge, so rocks, grass and foliage continue instead of smearing."""
    h, w = hole.shape
    src = np.where(hole, 1, 0).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ky, kx = np.nonzero(~hole)
    lut = np.zeros((labels.max() + 1, 2), np.int32)
    lut[labels[ky, kx]] = np.stack([ky, kx], 1)
    hy, hx = np.nonzero(hole)
    by, bx = lut[labels[hy, hx]].T
    my, mx = 2 * by - hy, 2 * bx - hx
    ok = (my >= 0) & (my < h) & (mx >= 0) & (mx < w)
    my, mx = np.where(ok, my, by), np.where(ok, mx, bx)
    bad = hole[my, mx]
    my, mx = np.where(bad, by, my), np.where(bad, bx, mx)
    out = img.copy()
    out[hy, hx] = img[my, mx]
    return out


def textured_fill(bgr, hole):
    """Telea for the colour, mirrored neighbours for the grain on top of it."""
    base = inpaint(bgr, hole).astype(np.float32)
    mir = mirror_fill(bgr, hole).astype(np.float32)
    detail = mir - cv2.GaussianBlur(mir, (0, 0), 4)
    soft = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 2)[..., None]
    out = bgr.astype(np.float32) * (1 - soft) + (base + detail) * soft
    return np.clip(out, 0, 255).astype(np.uint8)


def extend(values, known):
    """Push-pull: fill values outside `known` from the known ones, smoothly."""
    v = (values * known).astype(np.float32)
    w = known.astype(np.float32)
    pyr = [(v, w)]
    while min(v.shape) > 8:
        v = cv2.resize(v, (v.shape[1] // 2, v.shape[0] // 2), interpolation=cv2.INTER_AREA)
        w = cv2.resize(w, (w.shape[1] // 2, w.shape[0] // 2), interpolation=cv2.INTER_AREA)
        pyr.append((v, w))
    f = np.divide(pyr[-1][0], pyr[-1][1], out=np.full_like(pyr[-1][0], float(values[known].mean())), where=pyr[-1][1] > 1e-6)
    for v, w in reversed(pyr[:-1]):
        up = cv2.resize(f, (v.shape[1], v.shape[0]), interpolation=cv2.INTER_LINEAR)
        f = v + (1 - w) * up
        f = np.where(w > 1e-6, f / np.maximum(w + (1 - w), 1e-6), up)
    return f


def build(work, verbose=False):
    bgr = cv2.imread(os.path.join(work, "source.png"))
    d = np.load(os.path.join(work, "depth.npy")).astype(np.float32)
    h, w = d.shape

    # disparity with the sky at 0 (infinitely far, moves only with camera rotation)
    floor = float(np.percentile(d, 2))
    disp = np.clip((d - floor) / (1 - floor), 0, 1).astype(np.float32)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    # pull depth edges onto colour edges so outlines do not stay behind with the background
    disp = np.clip(guided_filter(gray, disp, 3, 2e-4), 0, 1).astype(np.float32)

    np.save(os.path.join(work, "disp.npy"), disp)
    cuts, edge = choose_cuts(disp)
    if verbose:
        print("cuts", [round(c, 3) for c in cuts])
    k7 = np.ones((7, 7), np.uint8)
    win_near, win_far = cv2.dilate(disp, k7), cv2.erode(disp, k7)
    bounds = [None] + cuts           # layer 0 = back plate, layer i starts at cuts[i-1]

    meta = {"width": w, "height": h, "cuts": cuts, "layers": []}
    previews = []
    for i, start in enumerate(bounds):
        nxt = cuts[i] if i < len(cuts) else None
        rgb, ld = bgr.copy(), disp.copy()
        if nxt is not None:
            # Inpaint behind the nearer content only in a band along the occlusion edges that
            # cross this cut: that is all a camera move can uncover. Where the surface runs on
            # continuously (ground, a body crossing the cut) the original pixels stay, so the
            # two layers carry the same colour and depth there and no seam can show.
            # Only pixels the nearer layer covers fully are replaced. Its soft edge pixels
            # keep their original colour here too, so with the camera at rest the composite
            # equals the source exactly instead of showing a blurred ring.
            # Edge pixels of the nearer layer are a mix of it and this layer: blend them
            # towards the fill by the nearer layer's coverage, so a camera move leaves no
            # bright specks of the nearer object behind and the composite at rest stays
            # within a quarter-mix of the source at the softest edge pixel.
            t = np.clip((disp - (nxt - 0.012)) / 0.024, 0, 1)
            cover = t * t * (3 - 2 * t)
            hole_full = cover > 0.02
            if HALO:
                hole_full = cv2.dilate(hole_full.astype(np.uint8), np.ones((2 * HALO + 1,) * 2, np.uint8)) > 0
            crossing = edge & (win_far < nxt) & (win_near >= nxt)
            band = cv2.dilate(crossing.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * REVEAL + 1,) * 2)) > 0
            fill_rgb = textured_fill(bgr, hole_full)
            fill_d = inpaint(disp, hole_full)
            fill_d = np.where(hole_full, cv2.GaussianBlur(fill_d, (0, 0), 6), fill_d)
            mix = np.where(band, cover, 0).astype(np.float32)
            rgb = np.clip(bgr * (1 - mix[..., None]) + fill_rgb * mix[..., None], 0, 255).astype(np.uint8)
            ld = (disp * (1 - mix) + fill_d * mix).astype(np.float32)
        if start is None:
            alpha = np.ones((h, w), np.float32)
        else:
            t = np.clip((ld - (start - 0.012)) / 0.024, 0, 1)
            alpha = t * t * (3 - 2 * t)
            alpha = np.clip(guided_filter(gray, alpha.astype(np.float32), 2, 1e-4), 0, 1)
            alpha[alpha < 0.02] = 0
        if not alpha.any():
            continue
        name = f"layer_{len(meta['layers']):02d}"
        rgba = np.dstack([rgb, (alpha * 255 + 0.5).astype(np.uint8)])
        cv2.imwrite(os.path.join(work, name + ".png"), rgba)
        # The renderer intersects camera rays with this depth by iteration. Where the layer
        # is transparent its depth only steers that search, so replace it with a smooth
        # continuation of the layer's own surface: a jump to the far background there (the
        # gaps between harp strings) makes the search jump and smear the layer.
        warp_d = ld
        if start is not None:
            inside = alpha > 0.02
            if inside.any():
                ext = cv2.GaussianBlur(extend(ld, inside), (0, 0), 3)
                warp_d = np.where(inside, ld, ext)
        np.save(os.path.join(work, name + "_disp.npy"), warp_d.astype(np.float32))
        cov = alpha > 0.5
        rep = float(np.median(disp[cov & (disp >= (start or 0)) & (disp < (nxt or 2))])) if cov.any() else 0.0
        meta["layers"].append({"name": name, "start": start, "end": nxt, "disp": rep,
                               "coverage": round(float(cov.mean()), 4)})
        # preview: layer over a checkerboard
        chk = ((np.indices((h, w)).sum(0) // 24) % 2 * 40 + 60).astype(np.float32)[..., None]
        prev = rgb.astype(np.float32) * alpha[..., None] + chk * (1 - alpha[..., None])
        previews.append(cv2.resize(prev.astype(np.uint8), (w // 3, h // 3), interpolation=cv2.INTER_AREA))

    # Sky: the model saturates at its far limit, so the sky is the pixels at the depth
    # floor. It becomes its own layer under the plate (clouds can drift), filled downwards
    # behind the mountains so drifting never uncovers them.
    sky = (d < floor + 0.0004).astype(np.uint8)
    sky = cv2.morphologyEx(sky, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(sky)
    keep = [k for k in range(1, n) if stats[k, cv2.CC_STAT_TOP] == 0 and stats[k, cv2.CC_STAT_AREA] > 2000]
    sky = np.isin(lab, keep)
    if sky.mean() > 0.02:
        sky_a = np.clip(guided_filter(gray, sky.astype(np.float32), 2, 1e-4), 0, 1)
        sky_rgb = textured_fill(bgr, cv2.dilate((~sky).astype(np.uint8), np.ones((11, 11), np.uint8)) > 0)
        cv2.imwrite(os.path.join(work, "sky.png"), sky_rgb)
        plate = cv2.imread(os.path.join(work, "layer_00.png"), cv2.IMREAD_UNCHANGED)
        plate[..., 3] = ((1 - sky_a) * 255 + 0.5).astype(np.uint8)
        cv2.imwrite(os.path.join(work, "layer_00.png"), plate)
        meta["sky"] = {"file": "sky.png", "horizon": int(np.percentile(np.argmax(~sky, 0)[sky[0]], 90))}
        if verbose:
            print("sky layer, horizon row", meta["sky"]["horizon"])

    with open(os.path.join(work, "layers.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    cols = 3
    rows = -(-len(previews) // cols)
    sheet = np.zeros((rows * (h // 3), cols * (w // 3), 3), np.uint8)
    for k, p in enumerate(previews):
        y, x = divmod(k, cols)
        sheet[y * (h // 3):(y + 1) * (h // 3), x * (w // 3):(x + 1) * (w // 3)] = p
        cv2.putText(sheet, meta["layers"][k]["name"], (x * (w // 3) + 8, y * (h // 3) + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(work, "_layers_sheet.png"), sheet)
    cv2.imwrite(os.path.join(work, "_edges.png"), (edge * 255).astype(np.uint8))
    return meta


if __name__ == "__main__":
    print(json.dumps(build(sys.argv[1], verbose=True)["layers"], indent=1))
