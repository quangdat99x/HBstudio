"""Small helpers: time, slugs, JSON files, the Recycle Bin."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def strip_diacritics(text: str) -> str:
    """Vietnamese-aware ASCII folding: 'người khổng lồ' -> 'nguoi khong lo'."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", strip_diacritics(text or "").lower()).strip("-")
    return s[:max_len].strip("-") or "item"


def safe_filename(name: str) -> str:
    """A file name that keeps its extension and readable words but nothing a path could abuse."""
    name = Path(name or "").name
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    stem = re.sub(r"[^\w\-. ]+", "_", strip_diacritics(stem)).strip(" ._") or "file"
    ext = re.sub(r"[^a-z0-9.]", "", ext)[:10]
    return (stem[:90] + ext) or "file"


def read_json(path: Path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def send_to_trash(path: Path) -> None:
    """Move a file or folder to the Windows Recycle Bin (the user can still restore it). Raises OSError if the
    shell refuses. FOF_WANTNUKEWARNING makes Windows ask instead of silently deleting for good when an item is
    too big for the bin."""
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI, FOF_WANTNUKEWARNING = 3, 0x4, 0x10, 0x40, 0x400, 0x4000
    full = str(Path(path).resolve())
    if not Path(full).exists():
        raise OSError(f"không thấy: {full}")
    buf = ctypes.create_unicode_buffer(full, len(full) + 2)     # pFrom needs a double null terminator
    op = SHFILEOPSTRUCTW(hwnd=None, wFunc=FO_DELETE, pFrom=ctypes.cast(buf, wintypes.LPCWSTR), pTo=None,
                         fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI | FOF_WANTNUKEWARNING)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc or op.fAnyOperationsAborted or Path(full).exists():
        raise OSError(f"không chuyển được vào Thùng rác (mã {rc:#x}, file đang mở?): {Path(full).name}")


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"
