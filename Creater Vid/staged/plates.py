"""Staged scene, step 2: one coherent painting -> wide depth plates + light maps for the engine.

Inputs in <dir> (made by blockout.py and the image model):
  master.png      the finished painting, painted from blockout.png (one light, one perspective)
  camera.json     blockout camera: focal length, metric depth of each plate
  depth.npy       blockout depth (metres), used to turn the painting's relative depth into metres
  <plate>.png     for every plate behind another one: the same painting with everything nearer removed and
                  painted over by the image model (what a camera move reveals), e.g. far.png, mid_clean.png
  stage.json      which plates to build (see below)

stage.json:
  {"near_far_cut_m": 20,                       # depth splitting the ground plate from the far plate
   "plates": [
     {"name": "far",    "src": "far.png",       "where": "far"},               # whole image, fills behind
     {"name": "ground", "src": "mid_clean.png", "where": "near"},              # ground without people
     {"name": "mid",    "src": "master.png",    "where": "near", "minus": "fg"},# ground + people + chain
     {"name": "fg",     "src": "master.png",    "where": "fg"}],
   "fg": {"diff_with": "mid_clean.png", "region": [x0, y0, x1, y1]},          # painted foreground object
   "lights": {"chain": {...}, "aura": {...}}, "motion": {...}}

Outputs in <dir>/out/: <plate>.png (RGBA), <plate>_z.png (1/z, 16 bit in R/G), light.png, motion.png, stage_meta.json
Run with the bgremove Python.
"""
import json
import os
import sys
from collections import deque

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parallax"))
import depth as depth_mod  # noqa: E402
from layers import extend, guided_filter  # noqa: E402

ZMAX = 600.0


def rel_disp(img_path, work):
    os.makedirs(work, exist_ok=True)
    return depth_mod.estimate(img_path, work).astype(np.float64)


def fit_inverse_depth(d, z_ref, mask):
    """Relative disparity d -> metres: 1/z = a*d + b, fitted on pixels where z_ref is known (robust)."""
    m = mask & np.isfinite(z_ref) & (z_ref > 0)
    x, y = d[m], 1.0 / z_ref[m]
    keep = np.ones_like(x, bool)
    for _ in range(4):
        A = np.stack([x[keep], np.ones(keep.sum())], 1)
        a, b = np.linalg.lstsq(A, y[keep], rcond=None)[0]
        r = np.abs(a * x + b - y)
        keep = r < np.percentile(r, 80)
    inv = np.clip(a * d + b, 1.0 / ZMAX, None)
    return 1.0 / inv, (float(a), float(b))


def local_correct(z, z_ref, mask, sigma=70):
    """Bend an estimated depth toward the blockout geometry with a smooth ratio field: the painting keeps its
    small relief, the large shape (where the ground really is) follows the blockout."""
    m = (mask & np.isfinite(z_ref) & (z_ref > 0)).astype(np.float32)
    logr = np.where(m > 0, np.log(np.nan_to_num(z_ref, nan=1, posinf=1) / np.maximum(z, 1e-3)), 0).astype(np.float32)
    num = cv2.GaussianBlur(logr * m, (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)
    corr = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0)
    return z * np.exp(corr)


def enc_invz(z, tear=None):
    s = np.clip(1.0 / np.maximum(z, 1e-3), 0, 1)                  # 1/z, near limit 1 m
    q = np.round(s * 65535).astype(np.uint16)
    out = np.zeros(z.shape + (3,), np.uint8)
    out[..., 2] = (q >> 8).astype(np.uint8)
    out[..., 1] = (q & 255).astype(np.uint8)
    if tear is not None:
        out[..., 0] = tear.astype(np.uint8) * 255               # B: the mesh is cut here (depth jump)
    return out


def tear_map(z, ratio=1.07, grow=5):
    """Where the mesh is cut: the near side of a depth jump (something standing in front of a farther
    background), grown a little to reach the far-side vertices. Ground that is NEARER than what stands on it
    (in front of the feet) is never a cut, so figures stay attached where they touch the ground."""
    k = np.ones((5, 5), np.uint8)
    zmax = cv2.dilate(z.astype(np.float32), k)
    near_side = zmax > z.astype(np.float32) * ratio
    return cv2.dilate(near_side.astype(np.uint8), np.ones((grow, grow), np.uint8)).astype(bool)


def soft(mask, gray, r=3):
    a = guided_filter(gray, mask.astype(np.float32), r, 1e-4)
    return np.clip(a, 0, 1)


def geodesic(mask, seed):
    """Pixel distance from seed along a mask (BFS, 8-neighbour): parameter along a painted chain, rope..."""
    h, w = mask.shape
    dist = np.full((h, w), -1.0, np.float32)
    q = deque([seed])
    dist[seed[1], seed[0]] = 0
    nb = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (1, 1, 1.414), (-1, 1, 1.414), (1, -1, 1.414)]
    while q:
        x, y = q.popleft()
        d0 = dist[y, x]
        for dx, dy, c in nb:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and dist[ny, nx] < 0:
                dist[ny, nx] = d0 + c
                q.append((nx, ny))
    return dist


def main():
    d = sys.argv[1]
    st = json.load(open(os.path.join(d, "stage.json"), encoding="utf-8"))
    cam = json.load(open(os.path.join(d, "camera.json"), encoding="utf-8"))
    out = os.path.join(d, "out")
    os.makedirs(out, exist_ok=True)
    work = os.path.join(d, "work")
    M = cv2.imread(os.path.join(d, "master.png"))
    H, W = M.shape[:2]
    gray = cv2.cvtColor(M, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    zb = np.load(os.path.join(d, "depth.npy"))
    if zb.shape != (H, W):
        zb = cv2.resize(zb, (W, H), interpolation=cv2.INTER_NEAREST)
    cut = st.get("near_far_cut_m", 20.0)

    # master in metres, calibrated on the blockout (edges excluded: the painting is not pixel exact)
    dM = rel_disp(os.path.join(d, "master.png"), os.path.join(work, "master"))
    finite = np.isfinite(zb)
    edges = cv2.dilate(cv2.Canny((np.nan_to_num(np.log(zb), posinf=9) * 40).astype(np.uint8), 20, 60), np.ones((25, 25), np.uint8)) > 0
    zM, fitM = fit_inverse_depth(dM, zb, finite & ~edges)
    near = zM < cut
    if st.get("local_correct", True):
        zM = np.where(near, local_correct(zM, zb, near & (zb < cut) & ~edges), zM)
    print("master fit", fitM, "near share", round(near.mean(), 3))

    # foreground object: what the clean ground plate removed inside the given region
    fg = np.zeros((H, W), bool)
    if st.get("fg"):
        C = cv2.imread(os.path.join(d, st["fg"]["diff_with"]))
        diff = cv2.GaussianBlur(np.abs(M.astype(np.float32) - C.astype(np.float32)).mean(2), (0, 0), 6)
        x0, y0, x1, y1 = st["fg"]["region"]
        reg = np.zeros((H, W), bool)
        reg[y0:y1, x0:x1] = True
        fg = ((diff > st["fg"].get("thresh", 12)) & reg).astype(np.uint8)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((41, 41), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
        if n > 1:
            fg = (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
        # fill holes: everything not reachable from the outside of the object
        pad = np.pad(fg, 1)
        flood = pad.copy()
        cv2.floodFill(flood, None, (0, 0), 1)
        fg = (pad | (1 - flood))[1:-1, 1:-1]
        fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((71, 71), np.uint8))
        # snap the outline to the painting
        fg = soft(fg.astype(bool), gray, 6) > 0.5
        fg = fg.astype(bool)

    meta = {"size": [W, H], "f": cam["f"], "plates": [], "fit": fitM}
    zcache = {"master.png": zM}
    for pl in st["plates"]:
        src = pl["src"]
        img = cv2.imread(os.path.join(d, src))
        if src not in zcache:
            dS = rel_disp(os.path.join(d, src), os.path.join(work, os.path.splitext(src)[0]))
            # calibrate on the master where both images show the same thing (far part for the far plate,
            # near part for the clean ground plate), away from the removed objects
            same = (np.abs(img.astype(np.float32) - M.astype(np.float32)).mean(2) < 14) & ~cv2.dilate(fg.astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
            ref = (~near if pl["where"] == "far" else near) & same
            zS, fitS = fit_inverse_depth(dS, zM, ref)
            if pl["where"] == "near" and st.get("local_correct", True):
                nearS = zS < cut
                zS = np.where(nearS, local_correct(zS, zb, nearS & (zb < cut) & ~edges), zS)
            zcache[src] = zS
            print(pl["name"], "fit", fitS)
        z = zcache[src]
        if pl["where"] == "far":
            # exact master pixels where the master itself is far; painted fill only where it was hidden
            hidden = cv2.dilate(near.astype(np.uint8), np.ones((17, 17), np.uint8)).astype(bool)
            # wide blend: the master paints light around its figures (a glow on the cliff) that the far image
            # does not have; a narrow seam would leave a dark outline of each figure on the far plate
            wgt = np.maximum(cv2.GaussianBlur(hidden.astype(np.float32), (0, 0), pl.get("feather", 22)), hidden.astype(np.float32))[..., None]
            # thin hidden strips (around a figure standing against the far view) are filled from the master
            # itself, so light painted around the figure carries on; the image model's fill is for large areas
            from layers import textured_fill
            inM = textured_fill(M, hidden).astype(np.float32)
            dist = cv2.distanceTransform(hidden.astype(np.uint8), cv2.DIST_L2, 5)
            k = np.clip((dist - pl.get("thin_px", 70)) / 60, 0, 1)[..., None]
            fill = inM * (1 - k) + img.astype(np.float32) * k
            img = (M * (1 - wgt) + fill * wgt).astype(np.uint8)
            # depth from the painted far image itself everywhere (it has no people in it): taking the master's
            # depth next to the people would pull a ghost of their outline into the far plate
            z = np.maximum(z, cut * 0.9)
            if pl.get("compress"):
                # one far plate holds near cliffs and distant haze: squeeze its depth range so camera travel
                # moves it as a whole instead of tearing it apart (the near/far parallax stays)
                zc = float(np.median(z))
                z = zc * (z / zc) ** pl["compress"]
            alpha = np.ones((H, W), np.float32)
            if pl.get("split_sky"):
                # the sky becomes its own plate at infinity, painted on behind the cliffs, so the cliff tops
                # can move against it without being stretched into it
                sky = z > pl.get("sky_m", 200)
                sky = cv2.morphologyEx(sky.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
                from layers import textured_fill
                hole = cv2.dilate((~sky).astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
                sky_img = textured_fill(img, hole)
                cv2.imwrite(os.path.join(out, "sky.png"), np.dstack([sky_img, np.full((H, W), 255, np.uint8)]))
                meta["sky"] = {"file": "sky.png"}
                alpha = soft(~sky, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255)
                z = np.where(sky, np.median(z[~sky & (alpha > 0.5)]) if (~sky).any() else z, z)
                z = np.minimum(z, pl.get("sky_m", 200))
        elif pl["where"] == "near":
            zn = z
            a = zn < cut
            if pl.get("minus") == "fg":
                a &= ~fg
            alpha = soft(a, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255)
            z = np.minimum(z, cut)
            if pl.get("figures"):
                # people stand ON the ground of this plate: the surface is the clean ground's smooth depth, and
                # each figure is upright at the depth of the ground under its feet. Painted details lying on the
                # ground (a chain) keep the ground's depth. The mesh is then cut only along the figures' upper
                # outline, never where they touch the ground.
                fcfg = pl["figures"]
                zg = zcache[fcfg["ground"]]
                Cg = cv2.imread(os.path.join(d, fcfg["ground"]))
                diff = cv2.GaussianBlur(np.abs(img.astype(np.float32) - Cg.astype(np.float32)).mean(2), (0, 0), 2)
                bodies = (diff > fcfg.get("thresh", 20)).astype(np.uint8)
                if fcfg.get("boxes"):
                    # each figure only inside its box (from the blockout anchors): what lies on the ground
                    # outside it (a chain) keeps the ground's depth
                    inbox = np.zeros((H, W), np.uint8)
                    for bx0, by0, bx1, by1 in fcfg["boxes"]:
                        inbox[by0:by1, bx0:bx1] = 1
                    bodies &= inbox
                bodies = cv2.morphologyEx(bodies, cv2.MORPH_OPEN, np.ones((fcfg.get("open", 17),) * 2, np.uint8))
                if fcfg.get("boxes"):
                    # above the ground's far edge a figure is simply what is near: the depth estimate outlines it
                    # (arms, hair) better than the difference with the clean ground
                    gsolid = zg < cut
                    horizon = np.where(gsolid.any(0), gsolid.argmax(0), H)
                    above = np.arange(H)[:, None] < horizon[None, :] + 4
                    bodies |= (near & above & inbox.astype(bool)).astype(np.uint8)
                bodies = cv2.morphologyEx(bodies, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
                z = np.minimum(zg, cut).astype(np.float64)
                n, lab, stats, _ = cv2.connectedComponentsWithStats(bodies)
                figs = []
                for k in range(1, n):
                    if stats[k, cv2.CC_STAT_AREA] < fcfg.get("min_area", 1500):
                        continue
                    comp = lab == k
                    if (comp & cv2.dilate(fg.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)).any():
                        continue        # pieces of the foreground object, not people
                    # a figure is solid: fill the holes the difference left inside it
                    padc = np.pad(comp.astype(np.uint8), 1)
                    flood = padc.copy()
                    cv2.floodFill(flood, None, (0, 0), 1)
                    comp = (padc | (1 - flood))[1:-1, 1:-1].astype(bool)
                    comp = cv2.morphologyEx(comp.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)).astype(bool)
                    ys, xs = np.nonzero(comp)
                    feet = ys.max()
                    zf = float(np.median(zg[np.clip(feet + 4, 0, H - 1), xs[ys > feet - 6]]))
                    ids = fcfg.get("ids")
                    if ids:
                        # the blockout knows where each figure stands: its depth wins over the painting's estimate
                        bi = next((i for i, (bx0, by0, bx1, by1) in enumerate(fcfg["boxes"]) if bx0 <= xs.mean() <= bx1 and by0 <= ys.mean() <= by1), None)
                        anc = cam["anchors"].get(ids[bi]) if bi is not None else None
                        if anc:
                            zf = float(max(v[2] for v in anc.values()))
                    grown = cv2.dilate(comp.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
                    z[grown] = zf
                    zcache["_fig"] = zcache.get("_fig", np.zeros((H, W), bool)) | grown
                    figs.append({"box": [int(xs.min()), int(ys.min()), int(xs.max()), int(feet)], "z": zf})
                meta.setdefault("figures", {})[pl["name"]] = figs
                z = cv2.GaussianBlur(z.astype(np.float32), (0, 0), 1.2)
        else:  # fg
            alpha = soft(fg, gray)
            z = np.where(fg, zM, np.median(zM[fg]) if fg.any() else 5)
        tear = None
        if pl["where"] != "far":
            # outside its own pixels a plate continues its own surface smoothly (no wall at the alpha edge);
            # real jumps inside it (a man in front of the ground) are cut
            solid = alpha > 0.5
            if solid.any() and not solid.all():
                # the outer rim of a plate takes the continuation of its interior surface: the estimated depth
                # ramps toward the background there and would make spikes when the camera moves
                inner = cv2.erode(solid.astype(np.uint8), np.ones((pl.get("rim", 13),) * 2, np.uint8)).astype(bool)
                if pl.get("figures"):
                    inner |= solid & zcache.get("_fig", np.zeros_like(solid))      # figures keep their own depth
                base_src = inner if inner.any() else solid
                z = np.where(inner, z, cv2.GaussianBlur(extend(z.astype(np.float32), base_src), (0, 0), 3))
            tear = tear_map(z, pl.get("tear_ratio", 1.06)) & (cv2.dilate(solid.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)

            if pl["where"] == "near" and not pl.get("figures"):
                tear[:] = False          # a bare ground plate is one continuous surface
        rgba = np.dstack([img, (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)])
        cv2.imwrite(os.path.join(out, f"{pl['name']}.png"), rgba)
        cv2.imwrite(os.path.join(out, f"{pl['name']}_z.png"), enc_invz(z, tear))
        meta["plates"].append({"name": pl["name"], "file": f"{pl['name']}.png", "zfile": f"{pl['name']}_z.png",
                               "z_median": float(np.median(z[alpha > 0.5])) if (alpha > 0.5).any() else 0})

    # ---- light maps on painted details (R = mask, G = parameter along it, B = second mask)
    light = np.zeros((H, W, 3), np.float32)
    motion = np.zeros((H, W, 3), np.float32)
    L = st.get("lights", {})
    if "chain" in L:
        c = L["chain"]
        C = cv2.imread(os.path.join(d, c["diff_with"]))
        diff = np.abs(M.astype(np.float32) - C.astype(np.float32)).mean(2)
        changed = (cv2.GaussianBlur(diff, (0, 0), 1.5) > c.get("thresh", 22)) & ~fg
        hsv = cv2.cvtColor(M, cv2.COLOR_BGR2HSV).astype(np.float32)
        metal = (hsv[..., 0] > 5) & (hsv[..., 0] < 30) & (hsv[..., 1] > 60) & (hsv[..., 2] > 35)
        bodies = cv2.morphologyEx(changed.astype(np.uint8), cv2.MORPH_OPEN, np.ones((c.get("open", 17),) * 2, np.uint8))
        bodies = cv2.dilate(bodies, np.ones((5, 5), np.uint8)).astype(bool)        # robes, skin: thick changed areas
        chain = changed & ~bodies & metal
        x0, y0, x1, y1 = c["region"]
        reg = np.zeros((H, W), bool)
        reg[y0:y1, x0:x1] = True
        chain &= reg
        if c.get("tube"):
            # painted metal inside a tube around the given path (more reliable than the image difference)
            tube = np.zeros((H, W), np.uint8)
            cv2.polylines(tube, [np.array(c["path"], np.int32)], False, 1, int(c["tube"]) * 2)
            metal2 = (hsv[..., 0] > 4) & (hsv[..., 0] < 32) & (hsv[..., 1] > c.get("sat", 70)) & (hsv[..., 2] > 30)
            chain = tube.astype(bool) & metal2
            # how much a pixel looks like lit bronze: saturated warm highlights glow, cloth and skin barely
            strength = np.clip((hsv[..., 1] - c.get("sat", 70)) / 90, 0, 1) * np.clip((hsv[..., 2] - 40) / 140, 0, 1)
        chain = cv2.morphologyEx(chain.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(chain.astype(np.uint8))
        keep = [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= c.get("min_area", 60)]
        chain = np.isin(lab, keep)
        ys, xs = np.nonzero(chain)
        # parameter along the chain: arc length of the nearest point on the path given in stage.json
        # (the painted links are separate pieces, so a flood along the mask would stop at the first gap)
        path = np.array(c["path"], np.float32)
        seg = path[1:] - path[:-1]
        seglen = np.linalg.norm(seg, axis=1)
        cum = np.concatenate([[0], np.cumsum(seglen)])
        P = np.stack([xs, ys], 1).astype(np.float32)
        best = np.full(len(P), np.inf)
        upar = np.zeros(len(P))
        for i in range(len(seg)):
            t = np.clip(((P - path[i]) @ seg[i]) / max(seglen[i] ** 2, 1e-6), 0, 1)
            dd = np.linalg.norm(P - (path[i] + t[:, None] * seg[i]), axis=1)
            better = dd < best
            best[better] = dd[better]
            upar[better] = (cum[i] + t[better] * seglen[i]) / cum[-1]
        far_off = best > c.get("max_dist", 40)
        chain[ys[far_off], xs[far_off]] = False
        u = np.zeros((H, W), np.float32)
        u[ys[~far_off], xs[~far_off]] = upar[~far_off]
        gmax = float(cum[-1])
        meta["chain"] = {"path": c["path"], "length_px": gmax}
        print("chain px", int(chain.sum()), "path length", gmax)
        light[..., 0] = cv2.GaussianBlur(chain.astype(np.float32) * (strength if c.get("tube") else 1), (0, 0), 0.8)
        light[..., 1] = cv2.dilate(u.astype(np.float32), np.ones((3, 3), np.uint8))
    if "aura" in L:
        a = L["aura"]
        x0, y0, x1, y1 = a["region"]
        C = cv2.imread(os.path.join(d, a["diff_with"]))
        diff = cv2.GaussianBlur(np.abs(M.astype(np.float32) - C.astype(np.float32)).mean(2), (0, 0), 2)
        body = np.zeros((H, W), np.uint8)
        body[y0:y1, x0:x1] = (diff[y0:y1, x0:x1] > 20)
        body = cv2.morphologyEx(body, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        wd = a.get("width", 41)
        ring = cv2.GaussianBlur(cv2.dilate(body, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (wd, wd))).astype(np.float32), (0, 0), wd / 2.5)
        light[..., 2] = np.clip(ring - body * 0.85, 0, 1) ** 1.6
        if a.get("sway"):
            ys2, xs2 = np.nonzero(body)
            top, bot = ys2.min(), ys2.max()
            grad = np.clip((np.arange(H)[:, None] - (top + 0.5 * (bot - top))) / (0.5 * (bot - top)), 0, 1)
            motion[..., 0] = cv2.GaussianBlur(body.astype(np.float32), (0, 0), 3) * grad ** 1.5
        meta["aura_box"] = [int(xs2.min()), int(top), int(xs2.max()), int(bot)] if a.get("sway") else None
    for name, box in st.get("motion", {}).items():
        x0, y0, x1, y1 = box
        mm = np.zeros((H, W), np.float32)
        mm[y0:y1, x0:x1] = 1
        motion[..., 1] = np.maximum(motion[..., 1], cv2.GaussianBlur(mm, (0, 0), 12) * near)
    cv2.imwrite(os.path.join(out, "light.png"), (np.clip(light, 0, 1) * 255).astype(np.uint8)[..., ::-1])
    cv2.imwrite(os.path.join(out, "motion.png"), (np.clip(motion, 0, 1) * 255).astype(np.uint8)[..., ::-1])
    np.save(os.path.join(work, "zM.npy"), zM.astype(np.float32))
    json.dump(meta, open(os.path.join(out, "stage_meta.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(meta["plates"], indent=1))


if __name__ == "__main__":
    main()
