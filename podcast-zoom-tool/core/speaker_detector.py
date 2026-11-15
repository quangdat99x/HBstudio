"""
Active Speaker Detection using Lip Movement Analysis.
Determines which person is currently speaking by analyzing
Mouth Aspect Ratio (MAR) changes over time.
"""

import numpy as np
from collections import defaultdict, deque
from typing import Optional, Dict
from .face_detector import FrameAnalysis


class SpeakerDetector:
    """Detects active speaker using lip movement patterns."""

    def __init__(self,
                 window_size: int = 15,
                 mar_threshold: float = 0.12,
                 activity_threshold: float = 0.25,
                 min_switch_frames: int = 15,
                 smoothing_alpha: float = 0.3):
        """
        Args:
            window_size: Number of frames to consider for activity detection
            mar_threshold: Minimum MAR to consider mouth as "open"
            activity_threshold: Min activity score to qualify as "speaking"
            min_switch_frames: Minimum frames before allowing speaker switch
            smoothing_alpha: EMA smoothing factor for MAR signal
        """
        self.window_size = window_size
        self.mar_threshold = mar_threshold
        self.activity_threshold = activity_threshold
        self.min_switch_frames = min_switch_frames
        self.smoothing_alpha = smoothing_alpha

        self._mar_history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self._smoothed_mar: Dict[int, float] = defaultdict(float)
        self._current_speaker: Optional[int] = None
        self._frames_since_switch: int = 0

    def update(self, frame_analysis: FrameAnalysis) -> Optional[int]:
        """
        Update speaker detection with new frame data.
        Returns the face_id of the current active speaker.
        """
        self._frames_since_switch += 1

        # Single face → it is unambiguously the speaker. Lock on immediately so
        # the camera tracks the only person without waiting for a MAR threshold.
        if len(frame_analysis.faces) == 1:
            only = frame_analysis.faces[0]
            self._smoothed_mar[only.face_id] = only.mouth_aspect_ratio
            self._mar_history[only.face_id].append(only.mouth_aspect_ratio)
            if only.face_id != self._current_speaker:
                self._current_speaker = only.face_id
                self._frames_since_switch = 0
            frame_analysis.active_speaker_id = self._current_speaker
            return self._current_speaker

        detected_ids = set()
        for face in frame_analysis.faces:
            fid = face.face_id
            detected_ids.add(fid)

            # EMA smoothing on raw MAR
            if fid in self._smoothed_mar:
                smoothed = (self.smoothing_alpha * face.mouth_aspect_ratio +
                            (1 - self.smoothing_alpha) * self._smoothed_mar[fid])
            else:
                smoothed = face.mouth_aspect_ratio

            self._smoothed_mar[fid] = smoothed
            self._mar_history[fid].append(smoothed)

        # Compute activity score for each detected face
        activity_scores = {}
        for fid in detected_ids:
            history = list(self._mar_history[fid])
            if len(history) < 3:
                activity_scores[fid] = 0.0
                continue

            # Activity = fraction of window where mouth is open
            active_count = sum(1 for m in history if m > self.mar_threshold)
            activity = active_count / len(history)

            # Variance bonus: speaking produces varying MAR
            variance = np.var(history) if len(history) > 1 else 0
            activity_scores[fid] = activity + variance * 10

        if not activity_scores:
            return self._current_speaker

        best_speaker = max(activity_scores, key=activity_scores.get)
        best_score = activity_scores[best_speaker]

        # No one clearly speaking → keep current
        if best_score < self.activity_threshold:
            return self._current_speaker

        # First speaker assignment
        if self._current_speaker is None:
            self._current_speaker = best_speaker
            self._frames_since_switch = 0
        elif best_speaker != self._current_speaker:
            # Switch only after minimum duration and with hysteresis
            if self._frames_since_switch >= self.min_switch_frames:
                current_score = activity_scores.get(self._current_speaker, 0)
                if best_score > current_score + 0.08:
                    self._current_speaker = best_speaker
                    self._frames_since_switch = 0

        frame_analysis.active_speaker_id = self._current_speaker
        return self._current_speaker

    def reset(self):
        """Reset detector state."""
        self._mar_history.clear()
        self._smoothed_mar.clear()
        self._current_speaker = None
        self._frames_since_switch = 0
