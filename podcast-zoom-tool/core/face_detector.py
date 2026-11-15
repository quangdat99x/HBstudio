"""
Face Detection & Tracking using MediaPipe Tasks API (FaceLandmarker).
Detects faces, extracts mouth landmarks, and computes Mouth Aspect Ratio (MAR)
for active speaker detection.

Uses the new mediapipe.tasks API instead of the deprecated mediapipe.solutions.
Auto-downloads the face_landmarker model on first run.
"""

import cv2
import os
import urllib.request
import numpy as np
import mediapipe as mp
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

# MediaPipe Tasks imports
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# Model download URL
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")


def ensure_model():
    """Download the FaceLandmarker model if not present."""
    if os.path.exists(MODEL_PATH):
        return MODEL_PATH

    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"[*] Downloading FaceLandmarker model (~5MB)...")
    print(f"   From: {MODEL_URL}")
    print(f"   To:   {MODEL_PATH}")

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"[OK] Model downloaded successfully!")
    except Exception as e:
        raise RuntimeError(
            f"Failed to download FaceLandmarker model: {e}\n"
            f"Please manually download from:\n  {MODEL_URL}\n"
            f"And place it at:\n  {MODEL_PATH}"
        )

    return MODEL_PATH


@dataclass
class _Pt:
    """A landmark re-expressed in full-frame normalized coordinates (same .x/.y/.z as MediaPipe's)."""
    x: float
    y: float
    z: float = 0.0


@dataclass
class FaceData:
    """Data for a single detected face in a frame."""
    face_id: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    center: Tuple[float, float]
    mouth_aspect_ratio: float
    expression_score: float = 0.0  # 0-1, higher = more expressive/engaging
    confidence: float = 1.0


@dataclass
class FrameAnalysis:
    """Analysis results for a single frame."""
    frame_index: int
    timestamp: float
    faces: List[FaceData]
    active_speaker_id: Optional[int] = None


class FaceDetector:
    """Detects and tracks faces using MediaPipe FaceLandmarker (Tasks API)."""

    def __init__(self, max_faces: int = 4, min_detection_confidence: float = 0.5):
        self.max_faces = max_faces

        # Ensure model is downloaded
        model_path = ensure_model()

        # Create FaceLandmarker with VIDEO mode
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        self._min_conf = min_detection_confidence

        self._face_tracker: Dict[int, Tuple[float, float]] = {}
        self._next_face_id = 0

        # Small-face fallback (wide studio shots such as The Basement): the landmarker's detector looks at the whole
        # frame scaled down, so a face ~8% of the frame width is missed. When the full frame finds nothing, look again
        # in crops: first around the faces the fallback found last time, else (every few frames) in overlapping tiles.
        self._crop_landmarker = None          # IMAGE mode: crops have no time continuity
        self._small_rois: List[Tuple[int, int, int, int]] = []
        self._tile_skip = 0

    # Overlapping tiles, each 60% of the frame: a face of ~150px in 1920 becomes ~13% of the tile and is found.
    _TILES = [(x, y) for y in (0.0, 0.4) for x in (0.0, 0.2, 0.4)]
    _TILE_SIZE = 0.6
    _TILE_EVERY = 5                           # analysed frames between two tile scans while nothing is found

    def _crop_lm(self):
        if self._crop_landmarker is None:
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=ensure_model()),
                running_mode=VisionRunningMode.IMAGE,
                num_faces=self.max_faces,
                min_face_detection_confidence=self._min_conf,
                min_face_presence_confidence=0.5,
            )
            self._crop_landmarker = FaceLandmarker.create_from_options(options)
        return self._crop_landmarker

    def _faces_in_crop(self, rgb: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> List[FaceData]:
        """Faces found inside rgb[y0:y1, x0:x1], with coordinates mapped back to the full frame."""
        h, w = rgb.shape[:2]
        crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
        if crop.shape[0] < 32 or crop.shape[1] < 32:
            return []
        res = self._crop_lm().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop))
        out = []
        cw, ch = x1 - x0, y1 - y0
        for lms in res.face_landmarks or []:
            mapped = [_Pt((x0 + lm.x * cw) / w, (y0 + lm.y * ch) / h, lm.z) for lm in lms]
            fd = self._process_face(mapped, w, h)
            if fd:
                out.append(fd)
        return out

    def _small_face_fallback(self, rgb: np.ndarray) -> List[FaceData]:
        h, w = rgb.shape[:2]
        regions = []
        for (x, y, bw, bh) in self._small_rois:          # around the faces found last time: a box 4x the face
            cx, cy, side = x + bw / 2, y + bh / 2, max(384, 4 * max(bw, bh))
            regions.append((int(max(0, cx - side / 2)), int(max(0, cy - side / 2)),
                            int(min(w, cx + side / 2)), int(min(h, cy + side / 2))))
        faces = self._merge([f for r in regions for f in self._faces_in_crop(rgb, *r)])
        if not faces:
            # tiles right after losing the faces, else only every few frames (B-roll with no face stays cheap)
            scan = bool(self._small_rois) or self._tile_skip == 0
            self._tile_skip = (self._tile_skip + 1) % self._TILE_EVERY
            if scan:
                tw, th = int(w * self._TILE_SIZE), int(h * self._TILE_SIZE)
                tiles = [(int(fx * w), int(fy * h), min(w, int(fx * w) + tw), min(h, int(fy * h) + th))
                         for fx, fy in self._TILES]
                faces = self._merge([f for r in tiles for f in self._faces_in_crop(rgb, *r)])
        self._small_rois = [f.bbox for f in faces]
        return faces

    @staticmethod
    def _merge(faces: List[FaceData]) -> List[FaceData]:
        """The same face seen in two overlapping crops counts once."""
        kept: List[FaceData] = []
        for f in sorted(faces, key=lambda f: -f.bbox[2] * f.bbox[3]):
            if all(np.hypot(f.center[0] - k.center[0], f.center[1] - k.center[1]) > 0.5 * max(k.bbox[2], k.bbox[3])
                   for k in kept):
                kept.append(f)
        return kept

    def detect_faces(self, frame: np.ndarray, frame_index: int, timestamp: float) -> FrameAnalysis:
        """Detect all faces in a frame and compute mouth metrics."""
        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Detect faces (timestamp in milliseconds for VIDEO mode)
        timestamp_ms = int(timestamp * 1000)
        results = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        faces = []
        if results.face_landmarks:
            for face_landmarks in results.face_landmarks:
                face_data = self._process_face(face_landmarks, w, h)
                if face_data:
                    faces.append(face_data)

        if faces:
            self._small_rois = []
        else:
            faces = self._small_face_fallback(rgb_frame)[:self.max_faces]

        self._assign_face_ids(faces)

        return FrameAnalysis(
            frame_index=frame_index,
            timestamp=timestamp,
            faces=faces
        )

    def _process_face(self, landmarks_list, img_w: int, img_h: int) -> Optional[FaceData]:
        """Process a single face's landmarks to extract bbox and MAR."""
        # In Tasks API, landmarks are NormalizedLandmark objects with .x, .y, .z
        xs = [lm.x * img_w for lm in landmarks_list]
        ys = [lm.y * img_h for lm in landmarks_list]

        x_min, x_max = int(min(xs)), int(max(xs))
        y_min, y_max = int(min(ys)), int(max(ys))

        # Add padding
        pad_x = int((x_max - x_min) * 0.15)
        pad_y = int((y_max - y_min) * 0.15)
        x_min = max(0, x_min - pad_x)
        y_min = max(0, y_min - pad_y)
        x_max = min(img_w, x_max + pad_x)
        y_max = min(img_h, y_max + pad_y)

        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
        center = ((x_min + x_max) / 2.0, (y_min + y_max) / 2.0)

        mar = self._calculate_mar(landmarks_list, img_w, img_h)
        expr = self._calculate_expression_score(landmarks_list, img_w, img_h, mar)

        return FaceData(face_id=-1, bbox=bbox, center=center,
                        mouth_aspect_ratio=mar, expression_score=expr)

    def _calculate_mar(self, landmarks, img_w: int, img_h: int) -> float:
        """
        Calculate Mouth Aspect Ratio.
        MAR = vertical_mouth_distance / horizontal_mouth_distance
        Higher MAR = mouth more open = likely speaking.
        
        Landmark indices (same as legacy Face Mesh 478 points):
          13 = upper lip top center (inner)
          14 = lower lip bottom center (inner)
          78 = left mouth corner
          308 = right mouth corner
        """
        if len(landmarks) < 400:
            return 0.0

        top = landmarks[13]
        bottom = landmarks[14]
        left = landmarks[78]
        right = landmarks[308]

        h_dist = np.sqrt((right.x * img_w - left.x * img_w) ** 2 +
                         (right.y * img_h - left.y * img_h) ** 2)
        if h_dist < 1:
            return 0.0

        v_dist = np.sqrt((top.x * img_w - bottom.x * img_w) ** 2 +
                         (top.y * img_h - bottom.y * img_h) ** 2)

        return v_dist / h_dist

    def _calculate_expression_score(self, landmarks, img_w: int, img_h: int,
                                     mar: float) -> float:
        """
        Calculate an expression engagement score (0.0 - 1.0).
        Scores higher for expressive faces: smiling, surprised, laughing,
        animated speaking. These make the best podcast thumbnails.

        Components:
          - Smile:         mouth corners raised relative to mouth center
          - Mouth openness: wide open mouth (laughing, reacting)
          - Eye wideness:   wider eyes = surprise/engagement
          - Eyebrow raise:  raised eyebrows = surprise/emphasis

        Landmark indices (MediaPipe Face Mesh 478 points):
          Mouth: 13 (upper lip), 14 (lower lip), 78 (L corner), 308 (R corner)
          Eyes:  159/145 (L top/bottom), 386/374 (R top/bottom)
                 33/133 (L inner/outer), 263/362 (R inner/outer)
          Eyebrows: 70 (L center), 300 (R center)
          Nose: 1 (tip)
          Face: 10 (forehead top), 152 (chin bottom)
        """
        if len(landmarks) < 400:
            return 0.0

        def px(lm):
            return lm.x * img_w, lm.y * img_h

        def dist(a, b):
            ax, ay = px(a)
            bx, by = px(b)
            return np.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

        # Face height for normalization
        face_h = dist(landmarks[10], landmarks[152])
        if face_h < 1:
            return 0.0

        # ── 1. Smile score ──
        # Mouth corners should be higher (lower y) than mouth center
        # when smiling. Compare corner y-avg to upper-lip y.
        l_corner_y = landmarks[78].y * img_h
        r_corner_y = landmarks[308].y * img_h
        upper_lip_y = landmarks[13].y * img_h
        lower_lip_y = landmarks[14].y * img_h
        mouth_center_y = (upper_lip_y + lower_lip_y) / 2
        corner_avg_y = (l_corner_y + r_corner_y) / 2
        # Positive = corners are above mouth center = smile
        smile_lift = (mouth_center_y - corner_avg_y) / face_h
        smile_score = min(1.0, max(0.0, smile_lift * 15))

        # ── 2. Mouth openness score ──
        # Use existing MAR — higher = more expressive
        # Typical talking MAR ~0.1-0.2, laughing/surprise ~0.3+
        mouth_score = min(1.0, mar / 0.4)

        # ── 3. Eye wideness score ──
        # Eye Aspect Ratio: vertical / horizontal for each eye
        l_eye_v = dist(landmarks[159], landmarks[145])
        l_eye_h = dist(landmarks[33], landmarks[133])
        r_eye_v = dist(landmarks[386], landmarks[374])
        r_eye_h = dist(landmarks[263], landmarks[362])

        l_ear = l_eye_v / l_eye_h if l_eye_h > 1 else 0
        r_ear = r_eye_v / r_eye_h if r_eye_h > 1 else 0
        avg_ear = (l_ear + r_ear) / 2
        # Normal EAR ~0.25-0.30, wide eyes ~0.35+
        eye_score = min(1.0, max(0.0, (avg_ear - 0.22) / 0.18))

        # ── 4. Eyebrow raise score ──
        # Distance from eyebrow to eye top, normalized by face height
        l_brow_lift = dist(landmarks[70], landmarks[159]) / face_h
        r_brow_lift = dist(landmarks[300], landmarks[386]) / face_h
        avg_brow_lift = (l_brow_lift + r_brow_lift) / 2
        # Normal ~0.04-0.06, raised ~0.07+
        brow_score = min(1.0, max(0.0, (avg_brow_lift - 0.04) / 0.05))

        # ── Weighted combination ──
        score = (
            smile_score * 0.35 +    # Smile is king for thumbnails
            mouth_score * 0.25 +    # Open mouth = energy
            eye_score * 0.20 +      # Wide eyes = surprise/engagement
            brow_score * 0.20       # Raised brows = emphasis
        )

        return min(1.0, max(0.0, score))

    def _assign_face_ids(self, faces: List[FaceData]):
        """Assign consistent face IDs across frames using centroid tracking."""
        if not faces:
            return

        if not self._face_tracker:
            for face in faces:
                face.face_id = self._next_face_id
                self._face_tracker[self._next_face_id] = face.center
                self._next_face_id += 1
            return

        # Match faces to tracked IDs by nearest centroid
        used_ids = set()
        unmatched = []

        for face in faces:
            best_id, best_dist = -1, float('inf')
            for tid, tc in self._face_tracker.items():
                if tid in used_ids:
                    continue
                dist = np.sqrt((face.center[0] - tc[0]) ** 2 +
                               (face.center[1] - tc[1]) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_id = tid

            if best_id >= 0 and best_dist < 300:
                face.face_id = best_id
                used_ids.add(best_id)
            else:
                unmatched.append(face)

        for face in unmatched:
            face.face_id = self._next_face_id
            self._next_face_id += 1

        self._face_tracker = {f.face_id: f.center for f in faces}

    def reset(self):
        """Reset tracker state."""
        self._face_tracker.clear()
        self._next_face_id = 0

    def close(self):
        """Release the landmarker resources."""
        if self._landmarker:
            self._landmarker.close()
        if self._crop_landmarker:
            self._crop_landmarker.close()
