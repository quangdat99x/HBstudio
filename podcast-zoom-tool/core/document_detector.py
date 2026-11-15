"""
Document Detector - finds an on-screen document (picture-in-picture screen capture, image, article, chart)
in a podcast frame.

JRE-style shows put what the producer pulls up into a rectangular inset over the camera shot (often bottom-right),
or cut to it full screen. A face-tracking zoom crops that inset away, so the pipeline asks this detector first.

How: an inset is a rectangle whose sides are perfectly straight, long, axis-aligned edges. Camera footage has
long straight lines too (wood planks, the sign, the desk), but almost never four sides of a rectangle meeting at
corners. On a downscaled grey frame we keep only horizontal/vertical edge runs that are long and contiguous
(morphological opening with a long thin kernel), then look for a top+bottom pair spanning the same columns, closed
by at least one vertical side (the frame border may stand in for a side the inset touches).
The pipeline adds the temporal rules (a box must hold still for a while; a box present in nearly every frame of
the clip is part of the set, not a document).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class DocBox:
    x: float          # in full-frame pixels
    y: float
    w: float
    h: float

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def iou(self, other: "DocBox") -> float:
        x1, y1 = max(self.x, other.x), max(self.y, other.y)
        x2 = min(self.x + self.w, other.x + other.w)
        y2 = min(self.y + self.h, other.y + other.h)
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        union = self.w * self.h + other.w * other.h - inter
        return inter / union if union > 0 else 0.0


class DocumentDetector:
    """Stateless per-frame detection of the largest document rectangle."""

    def __init__(self, analysis_width: int = 640, edge_threshold: int = 12,
                 min_h_line: float = 0.18, min_v_line: float = 0.16,
                 min_area: float = 0.06, max_area: float = 0.97):
        self.aw = analysis_width
        self.edge_threshold = edge_threshold
        self.min_h_line = min_h_line      # fraction of frame width a horizontal side must span
        self.min_v_line = min_v_line      # fraction of frame height a vertical side must span
        self.min_area = min_area
        self.max_area = max_area

    # ---------------------------------------------------------------- lines
    @staticmethod
    def _segments(mask: np.ndarray, horizontal: bool) -> List[Tuple[int, int, int]]:
        """Connected long runs → (fixed coordinate, start, end) in analysis pixels."""
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        out = []
        for i in range(1, n):
            x, y, w, h, _ = stats[i]
            if horizontal:
                out.append((y + h // 2, x, x + w))
            else:
                out.append((x + w // 2, y, y + h))
        return out

    def _lines(self, img: np.ndarray):
        """Long straight horizontal / vertical edges. Gradients per colour channel (max over B, G, R): an inset's
        border often has the same brightness as what is behind it (dark frame on a red curtain), only the colour
        changes."""
        h, w = img.shape[:2]
        gy = np.max(np.abs(cv2.Sobel(img, cv2.CV_16S, 0, 1, ksize=3)), axis=2)
        gx = np.max(np.abs(cv2.Sobel(img, cv2.CV_16S, 1, 0, ksize=3)), axis=2)
        hm = (gy > self.edge_threshold * 4).astype(np.uint8)
        vm = (gx > self.edge_threshold * 4).astype(np.uint8)
        # bridge 1-2 px gaps (compression noise) along the line, then keep only long straight runs
        hm = cv2.morphologyEx(hm, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1)))
        vm = cv2.morphologyEx(vm, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
        hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(8, int(w * self.min_h_line)), 1))
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(8, int(h * self.min_v_line))))
        hl = cv2.morphologyEx(hm, cv2.MORPH_OPEN, hk)
        vl = cv2.morphologyEx(vm, cv2.MORPH_OPEN, vk)
        return self._segments(hl, True), self._segments(vl, False)

    # ---------------------------------------------------------------- rectangles
    def detect(self, frame: np.ndarray) -> Optional[DocBox]:
        fh, fw = frame.shape[:2]
        scale = self.aw / fw
        small = cv2.resize(frame, (self.aw, int(round(fh * scale))), interpolation=cv2.INTER_AREA)
        h, w = small.shape[:2]
        hs, vs = self._lines(small)
        tol = max(4, int(w * 0.012))
        # the frame border can close a side the inset touches
        hs_ext = hs + [(0, 0, w), (h - 1, 0, w)]
        vs_ext = vs + [(0, 0, h), (w - 1, 0, h)]

        def vert_side(x: int, y1: int, y2: int) -> bool:
            need = (y2 - y1) * 0.7
            return any(abs(vx - x) <= tol and min(b, y2) - max(a, y1) >= need for vx, a, b in vs_ext)

        best, best_area = None, 0
        for i, (ya, xa1, xa2) in enumerate(hs_ext):
            for yb, xb1, xb2 in hs_ext[i + 1:]:
                top, bot = (ya, yb) if ya < yb else (yb, ya)
                if bot - top < h * self.min_v_line:
                    continue
                if (ya in (0, h - 1)) and (yb in (0, h - 1)):
                    continue                                   # two frame borders = the whole frame, not a box
                x1, x2 = max(xa1, xb1), min(xa2, xb2)          # columns both sides cover
                if x2 - x1 < w * self.min_h_line:
                    continue
                # sides must start/end together (a rectangle), allowing the frame border
                if abs(xa1 - xb1) > tol * 3 or abs(xa2 - xb2) > tol * 3:
                    continue
                left, right = vert_side(x1, top, bot), vert_side(x2, top, bot)
                real_h = sum(1 for y in (ya, yb) if y not in (0, h - 1))
                real_v = sum(1 for ok, x in ((left, x1), (right, x2)) if ok and x not in (0, w - 1))
                # at least three sides, at least two of them drawn (not frame border), one of each direction
                if not (left or right) or real_h < 1 or real_v < 1 or (real_h + real_v) < 3 and \
                        not (left and right):
                    continue
                area = (x2 - x1) * (bot - top) / float(w * h)
                if not (self.min_area <= area <= self.max_area):
                    continue
                if area > best_area:
                    best_area, best = area, (x1, top, x2 - x1, bot - top)
        if best is None:
            return None
        x, y, bw, bh = best
        return DocBox(x / scale, y / scale, bw / scale, bh / scale)
