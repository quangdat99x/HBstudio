"""Layout of the media folder (setting media_root):

    <media_root>\\Full\\       full episode videos + their .transcript.json (drop new downloads here)
    <media_root>\\Full\\<ID - show>\\   same, sorted by show: a video put here belongs to that show whatever its name
    <media_root>\\Cutlists\\   cutlist_<EP>.json (old/backup copies in Cutlists\\_old)
    <media_root>\\Clips\\      one folder per episode with its clips, zoomed clips and thumb_NN folders
    <media_root>\\Tong-hop\\   compilation videos
    <media_root>\\_old\\       leftovers (.ytdl, empty thumb folders, ...)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

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
    """Create the sub-folders (cheap, safe to call at startup), including one Full\\<show> folder per podcast."""
    for d in (full_dir(), cutlists_dir(), clips_dir(), tonghop_dir()):
        d.mkdir(parents=True, exist_ok=True)
    from . import podcasts
    taken = {d.name.lower() for d in full_dir().iterdir() if d.is_dir()}
    for prof in podcasts.all_profiles():
        if not _has_show_dir(prof["id"], taken):
            (full_dir() / show_dir_name(prof)).mkdir(exist_ok=True)


# ---------------------------------------------------------------- Full\<show>\ : one folder per podcast
# A video put into Full\<ID - Name>\ belongs to that show, whatever its file name looks like (downloads from other
# programs, shows without a file name pattern). Videos straight in Full\ still work through the file name patterns.
_BAD_CHARS = '<>:"/\\|?*'


def show_dir_name(prof: dict) -> str:
    name = "".join("_" if ch in _BAD_CHARS else ch for ch in (prof.get("name") or "")).strip(" .")
    return f"{prof['id']} - {name}" if name and name.upper() != prof["id"] else prof["id"]


def show_of_dir_name(dirname: str) -> Optional[str]:
    """'WHYFILES - The Why Files' / 'WHYFILES' / 'The Why Files' → 'WHYFILES'; None when no show has that folder."""
    from . import podcasts
    d = dirname.strip().lower()
    head = d.split(" - ", 1)[0].strip()
    for prof in podcasts.all_profiles():
        if head == prof["id"].lower() or d == (prof.get("name") or "").strip().lower() \
                or d == show_dir_name(prof).lower():
            return prof["id"]
    return None


def _has_show_dir(podcast_id: str, names: set) -> bool:
    return any(show_of_dir_name(n) == podcast_id for n in names)


def full_show_dirs() -> list[tuple[Path, str]]:
    """[(Full\\<show folder>, podcast_id)] for the show folders that exist."""
    root = full_dir()
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir():
            pid = show_of_dir_name(d.name)
            if pid:
                out.append((d, pid))
    return out


def full_dirs() -> list[Path]:
    """Full\\ itself, then every show folder inside it."""
    return [full_dir()] + [d for d, _ in full_show_dirs()]


def show_of_path(p: Path) -> Optional[str]:
    """Podcast id of a file that sits in a Full\\<show>\\ folder, else None."""
    p = Path(p)
    try:
        if p.parent.parent.resolve() != full_dir().resolve():
            return None
    except OSError:
        return None
    return show_of_dir_name(p.parent.name)


def full_videos() -> list[Path]:
    """Every episode video in Full\\ and its show folders (no partial downloads)."""
    from . import config
    out = []
    for d in full_dirs():
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in config.VIDEO_EXTS and not p.name.endswith(".part"):
                out.append(p)
    return out
