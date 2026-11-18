"""Thư mục data của MÁY NÀY và format chung của nó (giống nhau trên mọi máy).

Mỗi máy chọn một thư mục gốc (ổ nào cũng được), ghi trong C:\\Tool\\data_root.local.json (không lên Git):
    {"data_root": "D:\\\\DATA TOOL"}

Bên trong luôn theo cùng một format, nên chép data giữa hai máy chỉ cần chép đúng thư mục con:

    <data_root>\\YouTube\\Full\\              video tập đầy đủ + <tên video>.transcript.json      (Studio)
    <data_root>\\YouTube\\Full\\<MÃ - Show>\\  như trên, chia theo show: video thả vào là tập của show đó (Studio)
    <data_root>\\YouTube\\Cutlists\\          cutlist_<TẬP>.json                                  (Studio)
    <data_root>\\YouTube\\Clips\\<tập>\\      clip, bản zoom, thumbnail, _studio.json của tập     (Studio)
    <data_root>\\YouTube\\Tong-hop\\          video tổng hợp                                      (Studio)
    <data_root>\\VideoLab\\creater-projects\\<dự án>\\   một dự án, có project.json              (Creater Vid)

Không có file data_root.local.json: các tool dùng đường dẫn trong Cài đặt của chúng như trước.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
CONFIG_FILE = TOOL_DIR / "data_root.local.json"

# tên -> đường dẫn con trong data_root
LAYOUT = {
    "studio_media": ("YouTube",),
    "creater_projects": ("VideoLab", "creater-projects"),
}
STUDIO_SUBDIRS = ("Full", "Cutlists", "Clips", "Tong-hop")


def data_root() -> Path | None:
    """Thư mục data của máy này, None khi chưa chọn."""
    env = os.environ.get("TOOL_DATA_ROOT")             # cho test
    if env:
        return Path(env)
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("data_root")
    except (OSError, ValueError):
        return None
    return Path(raw) if raw else None


def path(name: str) -> Path | None:
    root = data_root()
    return root.joinpath(*LAYOUT[name]) if root else None


def ensure_layout(root: Path | None = None) -> list[Path]:
    """Tạo các thư mục của format chung (không đụng gì đã có). Trả về danh sách thư mục."""
    root = Path(root) if root else data_root()
    if root is None:
        return []
    media = root.joinpath(*LAYOUT["studio_media"])
    dirs = [media / d for d in STUDIO_SUBDIRS] + [root.joinpath(*LAYOUT["creater_projects"])]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def set_data_root(root: str | Path) -> Path:
    root = Path(str(root).strip().strip('"')).expanduser()
    if not root.is_absolute():
        raise ValueError("cần đường dẫn đầy đủ, ví dụ D:\\DATA TOOL")
    ensure_layout(root)
    CONFIG_FILE.write_text(json.dumps({"data_root": str(root)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def describe() -> dict:
    root = data_root()
    return {"data_root": str(root) if root else "", "config_file": str(CONFIG_FILE),
            "studio_media": str(path("studio_media") or ""), "creater_projects": str(path("creater_projects") or ""),
            "exists": bool(root and root.is_dir())}
