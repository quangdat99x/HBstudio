"""The six steps of a documentary project: what each one does, which files it must leave behind, how those files
are checked after a run, and what the project page shows for each step.

The detailed instructions for Claude live in the rulebook (section 2): improving the rulebook improves the workflow
without touching this file. The file schemas below match rulebook section 11.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .util import read_json


@dataclass(frozen=True)
class Step:
    key: str
    num: int
    name: str
    icon: str
    goal: str
    does: tuple[str, ...]
    outputs: tuple[str, ...]
    gate: str
    spends: str
    rule: str = ""                      # rulebook section
    extra: tuple[str, ...] = field(default_factory=tuple)


STEPS: tuple[Step, ...] = (
    Step("script", 1, "Kịch bản", "📝",
         "Nghiên cứu nguồn, chốt luận đề, viết kịch bản có lời dẫn, trích dẫn và thời lượng.",
         ("Đọc tư liệu bạn đưa vào (sources/) và tra thêm trên web, ưu tiên nguồn gốc và nguồn học thuật",
          "Tách các khẳng định, đánh dấu cái nào đã kiểm chứng, cái nào còn tranh cãi",
          "Đề xuất 2–3 hướng dàn ý, chọn hướng hợp yêu cầu nhất",
          "Viết kịch bản theo hồi: lời dẫn, chữ trên màn hình, trích dẫn nguyên văn, ý tưởng hình ảnh, nhân vật",
          "Ước tính thời lượng và chi phí giọng đọc"),
         ("1_script/research.md", "1_script/sources.json", "1_script/script.json", "1_script/script.md"),
         "Duyệt = chốt nội dung phim. Sau đó mới tuyển nhân vật.",
         "Không tiêu credit Higgsfield.", "2.1"),
    Step("cast", 2, "Tuyển nhân vật", "🎭",
         "Lập danh sách vai, ngoại hình bám nguồn và niên đại, tư thế cần, ảnh thử vai để chọn.",
         ("Gom các nhân vật xuất hiện trong kịch bản: chính, phụ, đám đông, người dẫn",
          "Mỗi vai: mô tả, ngoại hình đúng niên đại, cách thể hiện (vẽ AI, ảnh tư liệu, bóng đen…), các tư thế cần",
          "Viết prompt ảnh gốc theo phong cách chung của phim",
          "Vẽ 1–2 ảnh thử vai rẻ cho mỗi vai chính và phụ để bạn chọn"),
         ("2_cast/cast.json", "2_cast/cast.md"),
         "Chọn ứng viên cho từng vai rồi Duyệt: ứng viên được chọn thành ảnh gốc của nhân vật.",
         "Ảnh thử vai rẻ, tối đa khoảng 10% ngân sách.", "2.2"),
    Step("scenes", 3, "Phân cảnh & bối cảnh", "🗺️",
         "Chia kịch bản thành các cảnh 3D, lập danh sách bối cảnh, ảnh cần vẽ (prompt, model, credit) và footage cần.",
         ("Chia các beat thành cảnh dựng được: bối cảnh, các lớp sâu, nhân vật và tư thế, máy quay, hiệu ứng, âm thanh",
          "Lập danh sách bối cảnh và tấm nền cần vẽ, dùng lại tối đa",
          "Lập danh sách ảnh cần vẽ: model, chất lượng, tỉ lệ, prompt hoàn chỉnh, credit ước tính",
          "Lập danh sách footage cần: hiệu ứng quay thật, tư liệu, clip phỏng vấn, giọng đọc, nhạc"),
         ("3_scenes/scenes.json", "3_scenes/scenes.md"),
         "Duyệt = duyệt danh sách ảnh và số credit sẽ tiêu ở bước 4.",
         "Không tiêu credit.", "2.3"),
    Step("images", 4, "Render hình ảnh", "🖼️",
         "Vẽ ảnh gốc nhân vật, biến thể, nền bối cảnh và đạo cụ; tách nền trên máy; đo điểm neo.",
         ("Kiểm tra số dư Higgsfield, ghi nhật ký credit",
          "Ảnh gốc từ ứng viên đã chọn, biến thể sửa từ ảnh gốc để giữ đúng nhân vật",
          "Nền bối cảnh, đạo cụ, lớp sương/ánh sáng",
          "Tách nền trên máy (0 credit), soát viền, ghép bảng xem nhanh",
          "Đo điểm neo (tay, chân, đỉnh núi…) để hiệu ứng bám đúng chỗ"),
         ("4_images/manifest.json",),
         "Xem gallery, bấm Làm lại cho ảnh chưa ưng (kèm ghi chú), rồi Duyệt.",
         "Tiêu credit Higgsfield theo danh sách đã duyệt ở bước 3.", "2.4"),
    Step("footage", 5, "Footage & âm thanh", "🎞️",
         "Footage có giấy phép (tải sau khi bạn duyệt), clip trích, lời dẫn bằng giọng đọc, kế hoạch nhạc và hiệu ứng âm thanh.",
         ("Đề xuất footage: hiệu ứng lửa/khói quay thật, tư liệu, clip phỏng vấn, kèm nguồn, giấy phép, dung lượng",
          "Chỉ tải những file bạn đã duyệt trên app, xử lý (cắt, khử nền đen, đo độ chập chờn)",
          "Thu lời dẫn ElevenLabs v4 một lần cho cả kịch bản, chọn bản tốt nhất bằng whisper",
          "Lên kế hoạch nhạc và hiệu ứng âm thanh (tự tổng hợp)"),
         ("5_footage/footage.json",),
         "Duyệt từng file footage trước khi tải. Footage và giọng đọc đủ rồi thì Duyệt.",
         "Giọng đọc ElevenLabs v4 khoảng 4,3 credit cho mỗi phút đọc.", "2.5"),
    Step("render", 6, "Dựng & render", "🎬",
         "Dựng các cảnh bằng engine, soát ảnh tĩnh, trộn âm thanh, render MP4 và QA.",
         ("Viết timeline, các cảnh 3D, hiệu ứng, chữ trên màn hình",
          "Soát ảnh tĩnh đầu/giữa/cuối mỗi cảnh và cắt cận các điểm neo",
          "Trộn nhạc, hiệu ứng, lời dẫn; master −15 LUFS",
          "Render out/<tên>_v<N>.mp4 (không ghi đè bản cũ), chạy QA trên chính file MP4"),
         ("6_render/render.json",),
         "Xem phim, góp ý qua chat để ra bản mới. Duyệt = chốt bản cuối.",
         "Không tiêu credit (render trên máy).", "2.6"),
)

STEP_KEYS = tuple(s.key for s in STEPS)
BY_KEY = {s.key: s for s in STEPS}

STATUS_LABELS = {
    "locked": "chưa tới", "ready": "sẵn sàng", "queued": "đang chờ", "running": "đang chạy",
    "review": "chờ duyệt", "approved": "đã duyệt", "failed": "lỗi",
}


def prev_step(key: str) -> str | None:
    i = STEP_KEYS.index(key)
    return STEP_KEYS[i - 1] if i > 0 else None


def next_step(key: str) -> str | None:
    i = STEP_KEYS.index(key)
    return STEP_KEYS[i + 1] if i + 1 < len(STEP_KEYS) else None


# ---------------------------------------------------------------- helpers
def _rel(d: Path, path: Path) -> str:
    return str(path.relative_to(d)).replace("\\", "/")


def _md(d: Path, rel: str) -> str:
    p = d / rel
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except OSError:
        return ""


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _list(x) -> list:
    return x if isinstance(x, list) else []


def _exists(d: Path, rel) -> bool:
    return bool(rel) and isinstance(rel, str) and (d / rel).is_file()


def mmss(sec: float) -> str:
    sec = int(round(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"


def credits_spent(d: Path) -> dict:
    """notes/credits.json written by Claude (rulebook 11.7): total and the latest known balance."""
    data = read_json(d / "notes" / "credits.json")
    if not isinstance(data, dict):
        return {"total": 0.0, "events": [], "balance": None}
    events = [e for e in _list(data.get("events")) if isinstance(e, dict)]
    total = _num(data.get("total"), sum(_num(e.get("credits")) for e in events))
    balance = next((e.get("balance_after") for e in reversed(events) if e.get("balance_after") is not None), None)
    return {"total": round(total, 2), "events": events, "balance": balance}


def latest_mtime(d: Path, step: Step) -> float:
    times = [(d / rel).stat().st_mtime for rel in step.outputs if (d / rel).exists()]
    return max(times) if times else 0.0


# ---------------------------------------------------------------- checks after a run
def check(step_key: str, d: Path, project: dict) -> tuple[list[str], str]:
    """(problems, one-line summary) of a step's outputs. Problems starting with "⚠" are warnings; any other
    problem means the step did not produce what it must."""
    step = BY_KEY[step_key]
    problems = [f"thiếu {rel}" for rel in step.outputs if not (d / rel).exists()]
    fn = globals().get(f"_check_{step_key}")
    summary = ""
    if fn:
        extra, summary = fn(d, project)
        problems += extra
    return problems, summary


def blocking(problems: list[str]) -> bool:
    return any(not p.startswith("⚠") for p in problems or [])


def _check_script(d: Path, p: dict) -> tuple[list[str], str]:
    out: list[str] = []
    s = read_json(d / "1_script" / "script.json")
    if not (d / "1_script" / "script.json").exists():
        return out, ""
    if not isinstance(s, dict):
        return ["script.json không đọc được (JSON lỗi)"], ""
    beats = [b for b in _list(s.get("beats")) if isinstance(b, dict)]
    if not beats:
        out.append("script.json chưa có beats")
    total = sum(_num(b.get("duration_sec")) for b in beats)
    target = _num(p.get("target_sec"))
    if target and total and abs(total - target) > 0.2 * target:
        out.append(f"⚠ tổng thời lượng {mmss(total)} lệch mục tiêu {mmss(target)} quá 20%")
    src = read_json(d / "1_script" / "sources.json")
    ids = {x.get("id") for x in _list((src or {}).get("sources")) if isinstance(x, dict)}
    missing = sorted({sid for b in beats for sid in _list(b.get("sources")) if sid not in ids})
    if missing and ids:
        out.append("⚠ beat dẫn nguồn không có trong sources.json: " + ", ".join(map(str, missing[:8])))
    summary = f"{len(beats)} beat · {mmss(total)}" + (f" / {mmss(target)}" if target else "") + (f" · {len(ids)} nguồn" if ids else "")
    return out, summary


def _check_cast(d: Path, p: dict) -> tuple[list[str], str]:
    c = read_json(d / "2_cast" / "cast.json")
    if not (d / "2_cast" / "cast.json").exists():
        return [], ""
    if not isinstance(c, dict):
        return ["cast.json không đọc được (JSON lỗi)"], ""
    chars = [x for x in _list(c.get("characters")) if isinstance(x, dict)]
    out = [] if chars else ["cast.json chưa có nhân vật"]
    cands = [x for ch in chars for x in _list(ch.get("candidates")) if isinstance(x, dict)]
    lost = [x.get("file") for x in cands if not _exists(d, x.get("file"))]
    if lost:
        out.append(f"⚠ {len(lost)} ảnh thử vai không thấy file: " + ", ".join(map(str, lost[:4])))
    choices = read_json(d / "2_cast" / "choices.json") or {}
    need = [ch for ch in chars if _list(ch.get("candidates"))]
    unchosen = [ch.get("name") or ch.get("id") for ch in need if ch.get("id") not in choices]
    if unchosen:
        out.append("⚠ chưa chọn ứng viên cho: " + ", ".join(map(str, unchosen[:8])))
    return out, f"{len(chars)} vai · {len(cands)} ảnh thử vai"


def _check_scenes(d: Path, p: dict) -> tuple[list[str], str]:
    s = read_json(d / "3_scenes" / "scenes.json")
    if not (d / "3_scenes" / "scenes.json").exists():
        return [], ""
    if not isinstance(s, dict):
        return ["scenes.json không đọc được (JSON lỗi)"], ""
    scenes = [x for x in _list(s.get("scenes")) if isinstance(x, dict)]
    locs = {x.get("id") for x in _list(s.get("locations")) if isinstance(x, dict)}
    assets = [x for x in _list(s.get("assets")) if isinstance(x, dict)]
    out = [] if scenes else ["scenes.json chưa có cảnh"]
    bad = sorted({x.get("location") for x in scenes if x.get("location") and x.get("location") not in locs})
    if bad:
        out.append("⚠ cảnh dùng bối cảnh không có trong locations: " + ", ".join(map(str, bad[:6])))
    est = sum(_num(a.get("est_credits")) for a in assets)
    budget = _num(p.get("credit_budget"))
    spent = credits_spent(d)["total"]
    if budget and est + spent > budget:
        out.append(f"⚠ ước tính {est:g} credit + đã tiêu {spent:g} vượt ngân sách {budget:g}")
    total = sum(_num(x.get("duration_sec")) for x in scenes)
    return out, f"{len(scenes)} cảnh · {mmss(total)} · {len(assets)} ảnh · ~{est:g} credit"


def _check_images(d: Path, p: dict) -> tuple[list[str], str]:
    m = read_json(d / "4_images" / "manifest.json")
    if not (d / "4_images" / "manifest.json").exists():
        return [], ""
    if not isinstance(m, dict):
        return ["manifest.json không đọc được (JSON lỗi)"], ""
    assets = [x for x in _list(m.get("assets")) if isinstance(x, dict)]
    done = [a for a in assets if a.get("status") == "done"]
    lost = [a.get("key") for a in done if not _exists(d, a.get("file"))]
    out = []
    if lost:
        out.append("ảnh báo xong nhưng không thấy file: " + ", ".join(map(str, lost[:6])))
    failed = [a.get("key") for a in assets if a.get("status") in ("failed", "redo", "pending")]
    if failed:
        out.append(f"⚠ {len(failed)} ảnh chưa xong: " + ", ".join(map(str, failed[:6])))
    return out, f"{len(done)}/{len(assets)} ảnh xong · {sum(_num(a.get('credits')) for a in assets):g} credit"


def _check_footage(d: Path, p: dict) -> tuple[list[str], str]:
    f = read_json(d / "5_footage" / "footage.json")
    if not (d / "5_footage" / "footage.json").exists():
        return [], ""
    if not isinstance(f, dict):
        return ["footage.json không đọc được (JSON lỗi)"], ""
    items = [x for x in _list(f.get("items")) if isinstance(x, dict)]
    decisions = read_json(d / "5_footage" / "approvals.json") or {}
    waiting = [i for i in items if i.get("status") == "proposed" and i.get("id") not in decisions]
    approved_missing = [i.get("id") for i in items if (decisions.get(i.get("id")) or {}).get("decision") == "approved"
                        and i.get("status") not in ("downloaded", "processed", "generated")]
    out = []
    if waiting:
        out.append(f"⚠ {len(waiting)} footage chờ bạn duyệt")
    if approved_missing:
        out.append("⚠ đã duyệt nhưng chưa tải: " + ", ".join(map(str, approved_missing[:6])))
    ready = [i for i in items if i.get("status") in ("downloaded", "processed", "generated")]
    return out, f"{len(ready)}/{len(items)} footage sẵn sàng" + (f" · {len(waiting)} chờ duyệt" if waiting else "")


def _check_render(d: Path, p: dict) -> tuple[list[str], str]:
    r = read_json(d / "6_render" / "render.json")
    if not (d / "6_render" / "render.json").exists():
        return [], ""
    if not isinstance(r, dict):
        return ["render.json không đọc được (JSON lỗi)"], ""
    versions = [v for v in _list(r.get("versions")) if isinstance(v, dict)]
    if not versions:
        return ["render.json chưa có bản render"], ""
    last = versions[-1]
    out = []
    if not _exists(d, last.get("file")):
        out.append(f"không thấy file {last.get('file')}")
    qa = last.get("qa") if isinstance(last.get("qa"), dict) else {}
    if qa and qa.get("ok") is False:
        out.append("⚠ QA báo lỗi ở bản mới nhất")
    name = Path(str(last.get("file") or "")).name
    return out, f"{len(versions)} bản · mới nhất {name}" + (" · QA OK" if qa.get("ok") else "")


# ---------------------------------------------------------------- what the project page shows
def view(step_key: str, d: Path, project: dict) -> dict:
    fn = globals().get(f"_view_{step_key}")
    return fn(d, project) if fn else {}


def _view_script(d: Path, p: dict) -> dict:
    s = read_json(d / "1_script" / "script.json")
    src = read_json(d / "1_script" / "sources.json")
    out = {"research_md": _md(d, "1_script/research.md"), "script_md": _md(d, "1_script/script.md"),
           "script": s if isinstance(s, dict) else None, "sources": [], "claims": []}
    if isinstance(src, dict):
        out["sources"] = [x for x in _list(src.get("sources")) if isinstance(x, dict)]
        out["claims"] = [x for x in _list(src.get("claims")) if isinstance(x, dict)]
    if out["script"]:
        beats = [b for b in _list(out["script"].get("beats")) if isinstance(b, dict)]
        t = 0.0
        for b in beats:
            b["_start"] = mmss(t)
            t += _num(b.get("duration_sec"))
        out["beats"] = beats
        out["total"] = mmss(t)
    return out


def _view_cast(d: Path, p: dict) -> dict:
    c = read_json(d / "2_cast" / "cast.json")
    choices = read_json(d / "2_cast" / "choices.json") or {}
    chars = [x for x in _list((c or {}).get("characters")) if isinstance(x, dict)] if isinstance(c, dict) else []
    for ch in chars:
        ch["_candidates"] = [x for x in _list(ch.get("candidates")) if isinstance(x, dict) and _exists(d, x.get("file"))]
        ch["_chosen"] = choices.get(ch.get("id"))
    return {"cast": c if isinstance(c, dict) else None, "characters": chars, "cast_md": _md(d, "2_cast/cast.md"),
            "choices": choices}


def _view_scenes(d: Path, p: dict) -> dict:
    s = read_json(d / "3_scenes" / "scenes.json")
    if not isinstance(s, dict):
        return {"scenes_md": _md(d, "3_scenes/scenes.md"), "data": None}
    scenes = [x for x in _list(s.get("scenes")) if isinstance(x, dict)]
    t = 0.0
    for x in scenes:
        x["_start"] = mmss(t)
        t += _num(x.get("duration_sec"))
    assets = [x for x in _list(s.get("assets")) if isinstance(x, dict)]
    return {"data": s, "scenes": scenes, "locations": [x for x in _list(s.get("locations")) if isinstance(x, dict)],
            "assets": assets, "needs": [x for x in _list(s.get("footage_needs")) if isinstance(x, dict)],
            "est": round(sum(_num(a.get("est_credits")) for a in assets), 2), "total": mmss(t),
            "scenes_md": _md(d, "3_scenes/scenes.md")}


IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
KIND_ORDER = ("character", "variant", "plate", "prop", "additive")
KIND_NAMES = {"character": "Nhân vật (ảnh gốc)", "variant": "Biến thể nhân vật", "plate": "Nền bối cảnh",
              "prop": "Đạo cụ", "additive": "Sương, ánh sáng", "other": "Khác"}


def _view_images(d: Path, p: dict) -> dict:
    m = read_json(d / "4_images" / "manifest.json")
    assets = [x for x in _list((m or {}).get("assets")) if isinstance(x, dict)] if isinstance(m, dict) else []
    groups: dict[str, list] = {}
    for a in assets:
        a["_file"] = a.get("file") if _exists(d, a.get("file")) else (a.get("raw") if _exists(d, a.get("raw")) else None)
        kind = a.get("kind") if a.get("kind") in KIND_ORDER else "other"
        groups.setdefault(kind, []).append(a)
    ordered = [(k, KIND_NAMES[k], groups[k]) for k in (*KIND_ORDER, "other") if k in groups]
    sheets = sorted((d / "4_images").glob("*.jpg")) if (d / "4_images").exists() else []
    loose = []
    if not assets and (d / "film" / "public" / "img").exists():
        loose = [_rel(d, f) for f in sorted((d / "film" / "public" / "img").iterdir()) if f.suffix.lower() in IMG_EXT]
    return {"manifest": m if isinstance(m, dict) else None, "groups": ordered, "count": len(assets),
            "done": sum(1 for a in assets if a.get("status") == "done"),
            "sheets": [_rel(d, s) for s in sheets], "loose": loose}


def _view_footage(d: Path, p: dict) -> dict:
    f = read_json(d / "5_footage" / "footage.json")
    decisions = read_json(d / "5_footage" / "approvals.json") or {}
    items = [x for x in _list((f or {}).get("items")) if isinstance(x, dict)] if isinstance(f, dict) else []
    for i in items:
        i["_decision"] = (decisions.get(i.get("id")) or {}).get("decision")
        i["_file"] = i.get("file") if _exists(d, i.get("file")) else None
    voice = (f or {}).get("voice") if isinstance(f, dict) and isinstance(f.get("voice"), dict) else None
    takes = []
    if voice:
        takes = [t for t in _list(voice.get("takes")) if isinstance(t, dict)]
        for t in takes:
            t["_file"] = t.get("file") if _exists(d, t.get("file")) else None
    return {"data": f if isinstance(f, dict) else None, "entries": items, "voice": voice, "takes": takes,
            "music": (f or {}).get("music") if isinstance(f, dict) else None,
            "waiting": sum(1 for i in items if i.get("status") == "proposed" and not i["_decision"])}


def _view_render(d: Path, p: dict) -> dict:
    r = read_json(d / "6_render" / "render.json")
    versions = [v for v in _list((r or {}).get("versions")) if isinstance(v, dict)] if isinstance(r, dict) else []
    for v in versions:
        v["_file"] = v.get("file") if _exists(d, v.get("file")) else None
        v["_sheet"] = v.get("sheet") if _exists(d, v.get("sheet")) else None
    known = {v.get("file") for v in versions}
    videos = []
    if (d / "out").exists():
        for f in sorted((d / "out").glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
            rel = _rel(d, f)
            if rel not in known:
                videos.append({"file": rel, "mb": round(f.stat().st_size / 1e6, 1)})
    stills = []
    for folder in (d / "film" / "out" / "stills", d / "out" / "review"):
        if folder.exists():
            stills += [_rel(d, f) for f in sorted(folder.glob("*.jpg"), key=lambda x: x.stat().st_mtime, reverse=True)[:12]]
    return {"versions": list(reversed(versions)), "videos": videos, "stills": stills[:12]}
