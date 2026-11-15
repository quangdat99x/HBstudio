"""Layout of the media folder (setting media_root):

    <media_root>\\Full\\       full episode videos + their .transcript.json (drop new downloads here)
    <media_root>\\Cutlists\\   cutlist_<EP>.json (old/backup copies in Cutlists\\_old)
    <media_root>\\Clips\\      one folder per episode with its clips, zoomed clips and thumb_NN folders
    <media_root>\\Tong-hop\\   compilation videos
    <media_root>\\_old\\       leftovers (.ytdl, empty thumb folders, ...)
"""
from __future__ import annotations

from pathlib import Path

from . import db

FULL, CUTLISTS, CLIPS, TONGHOP, OLD = "Full", "Cutlists", "Clips", "Tong-hop", "_old"


def root() -> Path:
    return Path(db.get_setting("media_root"))


def full_dir() -> Path:
    return root() / FULL


def cutlists_dir() -> Path:
    return root() / CUTLISTS


def clips_dir() -> Path:
    return root() / CLIPS


def tonghop_dir() -> Path:
    return root() / TONGHOP


def cutlist_path(episode_id: str) -> Path:
    return cutlists_dir() / f"cutlist_{episode_id}.json"


def ensure() -> None:
    """Create the sub-folders (cheap, safe to call at startup)."""
    for d in (full_dir(), cutlists_dir(), clips_dir(), tonghop_dir()):
        d.mkdir(parents=True, exist_ok=True)
