"""
Download history stored as CSV for minimal footprint.
"""
import os
import csv
import threading
from datetime import datetime
from config import HISTORY_FILE

FIELDS = ['video_id', 'title', 'url', 'filepath', 'resolution', 'date']
_lock = threading.Lock()


def load() -> list:
    """Load all download history entries."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def save(video_id: str, title: str, url: str, filepath: str, resolution: str):
    """Append a completed download to history."""
    file_exists = os.path.exists(HISTORY_FILE)
    with _lock:
        try:
            with open(HISTORY_FILE, 'a', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    'video_id': video_id,
                    'title': title,
                    'url': url,
                    'filepath': filepath,
                    'resolution': resolution,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                })
        except Exception:
            pass


def check(url: str, extract_id_fn=None) -> dict | None:
    """Check if a URL was previously downloaded."""
    if extract_id_fn:
        video_id = extract_id_fn(url)
    else:
        video_id = url
    for entry in load():
        if entry.get('video_id') == video_id:
            return entry
    return None


def clear():
    """Delete all history."""
    with _lock:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
