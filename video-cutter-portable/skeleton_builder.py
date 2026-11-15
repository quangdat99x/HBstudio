"""
skeleton_builder.py — Build a skeleton manifest.json from Whisper segments.

Used by video-cutter-portable when exporting clips.
Each exported clip gets a matching <clip>.manifest.json skeleton:
  - timing = "explicit", timestamps relative to clip start (t=0 = clip start)
  - prompt = "" for every segment  → ready for /viet-prompt-v2 skill
  - SHA1 checksum over locked fields (id, start_sec, end_sec, audio_text)

The manifest is consumed by podcast-zoom-tool (documentary builder) which
reads it instead of re-running Whisper when timing="explicit".
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Internal data types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _Line:
    """One transcript utterance, timestamps already relative to clip start."""
    start_sec: float
    end_sec: float
    text: str


@dataclass
class _Seg:
    id: int
    start_sec: float
    end_sec: float
    audio_text: str

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


# ─────────────────────────────────────────────────────────────────────────────
# Sentence-aware segment grouping
# ─────────────────────────────────────────────────────────────────────────────

_SENTENCE_END_RE = re.compile(r'[.?!](?:["\')\]]+)?\s*$')


def _ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END_RE.search(text))


def _merge_into_segments(
    lines: List[_Line],
    target_sec: float = 8.0,
    min_sec: float = 3.0,
    max_sec: float = 12.0,
) -> List[_Seg]:
    """
    Greedy merge: accumulate lines until target_sec, prefer sentence boundary.
    Mirrors the same algorithm in tools/transcript_to_skeleton.py.
    """
    if not lines:
        return []

    segs: List[_Seg] = []
    buf: List[_Line] = []

    def _flush():
        if not buf:
            return
        start = buf[0].start_sec
        end = buf[-1].end_sec
        text = re.sub(r'\s+', ' ', ' '.join(r.text for r in buf)).strip()
        segs.append(_Seg(
            id=len(segs) + 1,
            start_sec=round(start, 3),
            end_sec=round(end, 3),
            audio_text=text,
        ))
        buf.clear()

    for ln in lines:
        buf.append(ln)
        dur = buf[-1].end_sec - buf[0].start_sec

        if dur >= max_sec:
            _flush()
        elif dur >= target_sec and _ends_sentence(buf[-1].text):
            _flush()
        elif dur >= target_sec * 1.4:
            # Past sweet-spot, force close even without sentence boundary
            _flush()

    # Flush tail — merge into previous if too short
    if buf:
        dur = buf[-1].end_sec - buf[0].start_sec
        if dur < min_sec and segs:
            prev = segs[-1]
            tail_text = re.sub(r'\s+', ' ', ' '.join(r.text for r in buf)).strip()
            segs[-1] = _Seg(
                id=prev.id,
                start_sec=prev.start_sec,
                end_sec=round(buf[-1].end_sec, 3),
                audio_text=re.sub(r'\s+', ' ', f"{prev.audio_text} {tail_text}").strip(),
            )
        else:
            _flush()

    return segs


# ─────────────────────────────────────────────────────────────────────────────
# Preferred duration heuristic
# ─────────────────────────────────────────────────────────────────────────────

def _preferred_duration(seg: _Seg) -> int:
    d = seg.duration
    if d <= 4.5: return 4
    if d <= 6.5: return 6
    if d <= 8.5: return 7
    if d <= 10.5: return 9
    return 12


# ─────────────────────────────────────────────────────────────────────────────
# SHA1 locked-fields checksum (same contract as transcript_to_skeleton.py)
# ─────────────────────────────────────────────────────────────────────────────

LOCKED_FIELDS = ['id', 'start_sec', 'end_sec', 'audio_text']


def _compute_locked_sha1(seg_dicts: List[dict]) -> str:
    locked = [{k: s[k] for k in LOCKED_FIELDS if k in s} for s in seg_dicts]
    canonical = json.dumps(locked, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(canonical.encode('utf-8')).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_skeleton_from_whisper_segments(
    whisper_segs: List[dict],
    clip_start_sec: float = 0.0,
    target_sec: float = 8.0,
    min_sec: float = 3.0,
    max_sec: float = 12.0,
) -> Optional[dict]:
    """
    Build a skeleton manifest dict from a list of Whisper transcript segments.

    Args:
        whisper_segs:    List of {start: float, end: float, text: str}.
                         Timestamps are ABSOLUTE within the original video.
        clip_start_sec:  The clip's start time in the original video (seconds).
                         All timestamps are shifted so t=0 = clip start.
        target_sec:      Target shot duration for grouping (default 8s).
        min_sec / max_sec: Hard bounds for segmentation.

    Returns:
        dict ready for json.dumps(), or None if no usable segments.
    """
    if not whisper_segs:
        return None

    # Adjust timestamps to be relative to clip start
    lines: List[_Line] = []
    for s in whisper_segs:
        try:
            start_rel = max(0.0, float(s['start']) - clip_start_sec)
            end_rel = max(0.0, float(s['end']) - clip_start_sec)
        except (KeyError, TypeError, ValueError):
            continue
        text = str(s.get('text', '')).strip()
        if text and end_rel > start_rel:
            lines.append(_Line(start_sec=start_rel, end_sec=end_rel, text=text))

    if not lines:
        return None

    segs = _merge_into_segments(lines, target_sec=target_sec, min_sec=min_sec, max_sec=max_sec)
    if not segs:
        return None

    seg_dicts = [
        {
            'id': s.id,
            'start_sec': s.start_sec,
            'end_sec': s.end_sec,
            'audio_text': s.audio_text,
            'prompt': '',
            'preferred_duration_sec': _preferred_duration(s),
        }
        for s in segs
    ]

    locked_sha1 = _compute_locked_sha1(seg_dicts)
    total_dur = round(seg_dicts[-1]['end_sec'] - seg_dicts[0]['start_sec'], 3)

    return {
        'version': '3.0',
        'timing': 'explicit',
        # timestamps already relative to clip (t=0 = clip start)
        'clip_start_sec': 0.0,
        'total_segments': len(seg_dicts),
        'total_duration_sec': total_dur,
        '_locked_fields': LOCKED_FIELDS,
        '_locked_sha1': locked_sha1,
        '_skill_instructions': (
            "viet-prompt-v2 contract: ONLY use the Edit tool to fill 'prompt' "
            "and optionally add 'text_overlay'/'style'/'aesthetic_tail'. "
            "DO NOT modify id, start_sec, end_sec, audio_text. "
            "DO NOT use the Write tool. "
            "Process batches of 20 segments per turn. "
            "At the end, recompute SHA1 over locked fields and confirm it "
            "matches _locked_sha1 — if mismatch, the manifest is corrupted."
        ),
        'style': '',
        'aesthetic_tail': '',
        'segments': seg_dicts,
    }
