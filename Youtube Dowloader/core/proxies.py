"""
Proxy pool for YouTube traffic.

proxies.txt (next to app.py) lists one proxy per line, e.g.
    http://user:pass@1.2.3.4:8080
    socks5://user:pass@5.6.7.8:1080
    1.2.3.4:8080              (no scheme = http://)
Lines starting with # are ignored. An empty or missing file = no proxies, and
the tool behaves exactly as before (direct line / 4G dongle).

Each job keeps one proxy for its whole run, because YouTube media links only
work from the IP that fetched them. Jobs are spread round-robin, and a proxy
YouTube bot-checks is benched for PROXY_COOLDOWN seconds.
"""
import os
import threading
import time

from config import BASE_DIR, PROXY_COOLDOWN

PROXY_FILE = os.path.join(BASE_DIR, 'proxies.txt')

_lock = threading.Lock()
_cursor = 0
_benched: dict[str, float] = {}   # proxy -> time it may be used again
_cache: tuple[float, list[str]] = (-1.0, [])


def _normalize(line: str) -> str:
    line = line.strip()
    if not line or line.startswith('#'):
        return ''
    if '://' not in line:
        line = 'http://' + line
    return line


def load() -> list[str]:
    """Proxies from proxies.txt, re-read whenever the file changes."""
    global _cache
    try:
        mtime = os.path.getmtime(PROXY_FILE)
    except OSError:
        return []
    if mtime != _cache[0]:
        try:
            with open(PROXY_FILE, encoding='utf-8-sig') as f:
                items = [p for p in (_normalize(l) for l in f) if p]
        except OSError:
            items = []
        _cache = (mtime, list(dict.fromkeys(items)))
    return _cache[1]


def available() -> bool:
    return bool(load())


def pick(exclude=()) -> str:
    """Next usable proxy (round-robin, skipping benched and excluded ones), or ''."""
    global _cursor
    pool = load()
    if not pool:
        return ''
    now = time.time()
    with _lock:
        for _ in range(len(pool)):
            p = pool[_cursor % len(pool)]
            _cursor += 1
            if p in exclude or _benched.get(p, 0) > now:
                continue
            return p
    return ''


def bench(proxy: str) -> None:
    """YouTube bot-checked this proxy: rest it for a while."""
    if proxy:
        with _lock:
            _benched[proxy] = time.time() + PROXY_COOLDOWN


def mask(proxy: str) -> str:
    """Proxy without its password, for logs and the UI."""
    if '@' not in proxy:
        return proxy
    scheme, _, rest = proxy.partition('://')
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


def status() -> dict:
    pool = load()
    now = time.time()
    benched = sum(1 for p in pool if _benched.get(p, 0) > now)
    return {'total': len(pool), 'benched': benched, 'ready': len(pool) - benched}
