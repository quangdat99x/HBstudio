"""Cut a layer painted on a flat grey backdrop: remove exactly the backdrop, keep everything painted (people AND the
ground they stand on, which a salient-object model like BiRefNet would drop).

The backdrop colour is modelled per pixel (the model paints a slightly uneven grey), the backdrop region is the
low-difference area connected to the image border, edges get a soft alpha and the grey is un-mixed from them.
Usage: python greykey.py in.png out.png
"""
import sys

import cv2
import numpy as np


def guided(I, p, r, eps):
    mean = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1))
    mI, mp = mean(I), mean(p)
    a = (mean(I * p) - mI * mp) / (mean(I * I) - mI * mI + eps)
    return mean(a) * I + mean(mp - a * mI)


def key(img):
    h, w = img.shape[:2]
    f = img.astype(np.float32)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    border = np.zeros((h, w), bool)
    border[:6, :] = border[:, :6] = border[:, -6:] = True
    ref = np.median(f[border & (hsv[..., 1] < 30)], axis=0) if (border & (hsv[..., 1] < 30)).any() else np.array([128, 128, 128.0])
    greyish = (hsv[..., 1] < 26) & (np.abs(f - ref).mean(2) < 45)
    # smooth backdrop model from the grey pixels (normalized blur)
    m = greyish.astype(np.float32)
    num = cv2.GaussianBlur(f * m[..., None], (0, 0), 25)
    den = cv2.GaussianBlur(m, (0, 0), 25)[..., None]
    B = np.where(den > 1e-3, num / np.maximum(den, 1e-3), ref)
    d = np.abs(f - B).max(2)
    # backdrop = low difference AND connected to the border
    low = (d < 14).astype(np.uint8)
    n, lab = cv2.connectedComponents(low)
    touch = np.unique(lab[border & (low > 0)])
    bg = np.isin(lab, touch[touch > 0])
    bg = cv2.morphologyEx(bg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    # soft edge: difference ramp near the backdrop boundary
    near_bg = cv2.dilate(bg.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    soft = np.clip((d - 8) / 28, 0, 1)
    a = np.where(bg, 0.0, np.where(near_bg, soft, 1.0)).astype(np.float32)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    a = np.clip(guided(gray, a, 2, 1e-4), 0, 1)
    a[a < 0.02] = 0
    # un-mix the grey from the soft edge pixels
    aa = np.maximum(a, 1e-3)[..., None]
    F = np.clip((f - (1 - aa) * B) / aa, 0, 255)
    F = np.where(a[..., None] > 0.98, f, F)
    return np.dstack([F.astype(np.uint8), (a * 255 + 0.5).astype(np.uint8)])


if __name__ == "__main__":
    out = key(cv2.imread(sys.argv[1]))
    cv2.imwrite(sys.argv[2], out)
    print(sys.argv[2], "opaque", round(float((out[..., 3] > 128).mean()), 3))
