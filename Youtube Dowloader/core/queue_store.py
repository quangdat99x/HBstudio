"""
Danh sách chờ: link được nhập sẵn, mỗi link tải riêng khi người dùng bấm "Tải".

Lưu ở download_queue.json (riêng từng máy, không lên Git). Mỗi mục:
    id        mã ngắn
    url       link gốc
    video_id  mã video YouTube (để dò trùng với lịch sử)
    title     tên video, rỗng cho tới khi tải xong (không gọi YouTube lúc nhập để khỏi bị chặn)
    status    'pending' | 'downloading' | 'done' | 'error'
    added     thời điểm nhập
    done_at   thời điểm tải xong
    filepath  file đã tải
    error     lỗi lần tải cuối
"""
import os
import re
import json
import uuid
import threading
from datetime import datetime

from config import QUEUE_FILE

_lock = threading.Lock()
_URL_RE = re.compile(r'https?://[^\s<>"\']+')


def now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def load() -> list:
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list) -> None:
    tmp = QUEUE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUEUE_FILE)


def extract_urls(text: str) -> list:
    """Mỗi dòng một link; bỏ chữ thừa quanh link, bỏ dòng trống, bỏ trùng (giữ thứ tự)."""
    out, seen = [], set()
    for line in (text or '').splitlines():
        m = _URL_RE.search(line)
        if not m:
            continue
        url = m.group(0).rstrip('.,;)')
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def add(urls: list, extract_id_fn, history_check=None) -> dict:
    """Thêm link vào danh sách. Link đã có trong danh sách thì bỏ qua; link đã tải (có trong
    lịch sử) thì vào thẳng trạng thái 'done' kèm tên và file từ lịch sử."""
    with _lock:
        items = load()
        known = {it.get('video_id') or it.get('url') for it in items}
        added = already_done = skipped = 0
        for url in urls:
            vid = extract_id_fn(url) or url
            if vid in known:
                skipped += 1
                continue
            known.add(vid)
            item = {
                'id': uuid.uuid4().hex[:8],
                'url': url,
                'video_id': vid,
                'title': '',
                'status': 'pending',
                'added': now(),
                'done_at': None,
                'filepath': None,
                'error': None,
            }
            prev = history_check(url) if history_check else None
            if prev:
                item.update({
                    'status': 'done',
                    'title': prev.get('title') or '',
                    'filepath': prev.get('filepath'),
                    'done_at': prev.get('date'),
                })
                already_done += 1
            items.append(item)
            added += 1
        _save(items)
    return {'added': added, 'already_done': already_done, 'skipped': skipped, 'total': len(items)}


def get(item_id: str) -> dict | None:
    for it in load():
        if it['id'] == item_id:
            return it
    return None


def update(item_id: str, **fields) -> dict | None:
    with _lock:
        items = load()
        for it in items:
            if it['id'] == item_id:
                it.update(fields)
                _save(items)
                return it
    return None


def mark(item_id: str, status: str) -> dict | None:
    """Người dùng tự đánh dấu: 'done' hoặc 'pending'."""
    if status == 'done':
        return update(item_id, status='done', done_at=now(), error=None)
    return update(item_id, status='pending', done_at=None, error=None)


def remove(item_id: str) -> bool:
    with _lock:
        items = load()
        kept = [it for it in items if it['id'] != item_id]
        if len(kept) == len(items):
            return False
        _save(kept)
        return True


def remove_done() -> int:
    with _lock:
        items = load()
        kept = [it for it in items if it['status'] != 'done']
        _save(kept)
        return len(items) - len(kept)


def reset_stuck() -> None:
    """Server khởi động lại giữa lúc tải: mục 'downloading' quay về 'pending'."""
    with _lock:
        items = load()
        changed = False
        for it in items:
            if it.get('status') == 'downloading':
                it['status'] = 'pending'
                changed = True
        if changed:
            _save(items)
