"""Validate a cutlist produced by the headless selection run before anything gets cut."""
from __future__ import annotations

from ..util import hms_to_sec

HOOK_MIN, HOOK_MAX = 4.0, 30.0


def validate_cutlist(data: dict, duration_sec: float | None = None, expect_episode_id: str | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"errors": ["cutlist is not a JSON object"], "warnings": []}
    ep = data.get("episode") or {}
    if expect_episode_id and str(ep.get("id", "")).upper() != expect_episode_id.upper():
        errors.append(f"episode.id là {ep.get('id')!r}, phải là {expect_episode_id!r}")
    segs = data.get("segments")
    if not isinstance(segs, list) or not segs:
        return {"errors": errors + ["segments[] trống"], "warnings": warnings}
    by_rank: dict[int, dict] = {}
    parsed = []
    for i, s in enumerate(segs, 1):
        label = f"segments[{i}] {str(s.get('title', ''))[:50]!r}"
        try:
            st, en = hms_to_sec(s.get("start")), hms_to_sec(s.get("end"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{label}: timestamp lỗi ({e})")
            continue
        kind = (s.get("kind") or "").lower()
        if kind not in ("hook", "highlight"):
            errors.append(f"{label}: thiếu kind (hook|highlight)")
        if not str(s.get("title", "")).strip():
            errors.append(f"{label}: thiếu title")
        if en <= st:
            errors.append(f"{label}: end <= start")
        if duration_sec and en > duration_sec + 2:
            errors.append(f"{label}: end {s.get('end')} vượt quá thời lượng video ({int(duration_sec)}s)")
        rank = s.get("rank")
        if isinstance(rank, int):
            if rank in by_rank:
                errors.append(f"{label}: rank {rank} bị trùng")
            by_rank[rank] = s
        else:
            errors.append(f"{label}: rank phải là số nguyên")
        parsed.append((s, st, en, kind))
    ranks = sorted(by_rank)
    if ranks and ranks != list(range(1, len(ranks) + 1)):
        errors.append(f"rank không liên tục 1..N: {ranks}")
    highlights = [(s, st, en) for s, st, en, k in parsed if k == "highlight"]
    for s, st, en, kind in parsed:
        if kind != "hook":
            continue
        parent = by_rank.get(s.get("parent_rank"))
        if not parent or (parent.get("kind") or "").lower() != "highlight":
            errors.append(f"hook {str(s.get('title',''))[:40]!r}: parent_rank {s.get('parent_rank')} không trỏ tới highlight")
            continue
        pst, pen = hms_to_sec(parent["start"]), hms_to_sec(parent["end"])
        if st < pst - 2 or en > pen + 2:
            errors.append(f"hook {str(s.get('title',''))[:40]!r}: nằm ngoài đoạn cha ({parent['start']}–{parent['end']})")
        d = en - st
        if d < HOOK_MIN or d > HOOK_MAX:
            warnings.append(f"hook {str(s.get('title',''))[:40]!r}: dài {d:.0f}s, ngoài khoảng 5–25s")
    highlights.sort(key=lambda x: x[1])
    for (a, ast, aen), (b, bst, ben) in zip(highlights, highlights[1:]):
        if bst < aen - 1:
            warnings.append(f"highlight chồng lấn: {str(a.get('title',''))[:30]!r} và {str(b.get('title',''))[:30]!r}")
    if not highlights:
        errors.append("không có entry highlight nào")
    return {"errors": errors, "warnings": warnings, "highlights": len(highlights), "hooks": len(parsed) - len(highlights)}
