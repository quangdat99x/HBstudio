"""
Video Processing - handles crop computation and smooth "virtual camera"
movement that tracks the active speaker's face.

The camera uses an exponential-moving-average follow with two refinements
tuned for podcast face tracking:

  * Dead-zone  — ignore tiny target movements so the camera stays rock
                 steady while a face wobbles slightly (landmark jitter),
                 instead of trembling frame-to-frame.
  * Adaptive speed — pan slowly for small corrections (smooth, cinematic),
                 but accelerate when the target jumps a long way (a speaker
                 switch) so the camera catches up promptly instead of
                 drifting lazily across the frame.
"""

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class CropRegion:
    """Defines a crop region for a frame."""
    center_x: float
    center_y: float
    width: float
    height: float


class VideoProcessor:
    """Handles video crop/zoom with smooth camera panning."""

    def __init__(self, zoom_factor: float = 2.0, smoothing_speed: float = 0.05):
        """
        Args:
            zoom_factor: Zoom level (2.0 = 200% zoom = crop to 50% of frame)
            smoothing_speed: Base camera pan speed (0.01=very slow, 0.1=fast).
                Small corrections move at this speed; large jumps (speaker
                switches) ramp up toward `max_speed` automatically.
        """
        self.zoom_factor = zoom_factor
        self.smoothing_speed = smoothing_speed
        # Ceiling for the adaptive ramp on big jumps (speaker switch).
        self.max_speed = min(1.0, max(smoothing_speed * 4.0, 0.18))
        # Dead-zone as a fraction of crop width — movements smaller than this
        # are treated as jitter and ignored.
        self.dead_zone_ratio = 0.012
        # A jump this large (fraction of frame width) gets near-max speed.
        self.switch_scale = 0.22

        # Per-frame easing of the zoom level (documents / full frame change it).
        self.zoom_speed = 0.12

        self._current_x = None
        self._current_y = None
        self._current_z = None
        self._crop_w = None
        self._crop_h = None

    @staticmethod
    def _smoothstep(t: float) -> float:
        """Smooth 0→1 ramp (eases in and out)."""
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    def compute_crop(self, target, frame_w: int, frame_h: int) -> CropRegion:
        """
        Compute the smoothed crop region for this frame.

        `target` is (x, y) — the active speaker's face center — or (x, y, zoom) when the pipeline asks for a
        different zoom (a document on screen zooms less, a frame without faces shows everything).
        """
        target_x, target_y = target[0], target[1]
        target_z = target[2] if len(target) > 2 else self.zoom_factor

        # Zoom eases toward its target: quickly on a big change (face → document), so the document is whole
        # within ~0.5 s, and never overshoots.
        if self._current_z is None:
            self._current_z = target_z
        elif abs(target_z - self._current_z) > 1e-3:
            self._current_z += (target_z - self._current_z) * self.zoom_speed
            if abs(target_z - self._current_z) < 0.01:
                self._current_z = target_z

        crop_w = frame_w / self._current_z
        crop_h = frame_h / self._current_z
        self._crop_w = crop_w
        self._crop_h = crop_h

        # First frame: snap straight to the target.
        if self._current_x is None:
            self._current_x = target_x
            self._current_y = target_y
        else:
            dx = target_x - self._current_x
            dy = target_y - self._current_y
            dist = (dx * dx + dy * dy) ** 0.5

            dead_zone = crop_w * self.dead_zone_ratio
            if dist > dead_zone:
                # Adaptive speed: ramp from base → max as the jump grows.
                jump_frac = dist / frame_w
                ramp = self._smoothstep(jump_frac / self.switch_scale)
                speed = self.smoothing_speed + (self.max_speed - self.smoothing_speed) * ramp

                self._current_x += dx * speed
                self._current_y += dy * speed

        # Clamp the crop window to stay inside the frame.
        half_w, half_h = crop_w / 2, crop_h / 2
        cx = max(half_w, min(frame_w - half_w, self._current_x))
        cy = max(half_h, min(frame_h - half_h, self._current_y))

        return CropRegion(center_x=cx, center_y=cy, width=crop_w, height=crop_h)

    def apply_crop(self, frame: np.ndarray, crop: CropRegion) -> np.ndarray:
        """Crop frame and resize back to original dimensions."""
        h, w = frame.shape[:2]

        x1 = max(0, int(crop.center_x - crop.width / 2))
        y1 = max(0, int(crop.center_y - crop.height / 2))
        x2 = min(w, int(x1 + crop.width))
        y2 = min(h, int(y1 + crop.height))

        cropped = frame[y1:y2, x1:x2]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)

    def reset(self):
        """Reset camera position."""
        self._current_x = None
        self._current_y = None
        self._current_z = None
        self._crop_w = None
        self._crop_h = None
