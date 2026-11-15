"""Pipeline graph for the /pipeline page: the stages as nodes, live counts from the DB, editable settings per node.

The graph mirrors the real orchestrator (studio/pipeline/orchestrator.py) instead of describing a separate workflow:
node state comes from `episodes.stage` and the `jobs` table, and node settings are the same keys the Settings page edits.
"""
from __future__ import annotations

from . import config, db

# Each field: (setting key, label, kind) with kind "bool" | "text" | "number" | a list of choices.
MODELS = ["", "fable", "opus", "sonnet", "haiku"]
EFFORTS = ["", "low", "medium", "high", "xhigh", "max"]

NODES = [
    {"id": "intake", "label": "Nạp video", "icon": "📥", "x": 40, "y": 160, "job": "download", "states": ["new", "downloading"],
     "desc": "Link YouTube, file chọn tay hoặc thư mục media được theo dõi.",
     "fields": [("watch_enabled", "Theo dõi thư mục media", "bool"),
                ("file_stable_seconds", "Chờ file đứng yên (giây)", "number")]},
    {"id": "transcribe", "label": "Transcript", "icon": "📝", "x": 260, "y": 160, "job": "transcribe", "states": ["transcribing"],
     "desc": "Whisper tạo transcript (bỏ qua nếu đã có file).",
     "fields": [("whisper_model", "Model Whisper", ["large-v3", "large-v3-turbo", "medium", "small"]),
                ("whisper_language", "Ngôn ngữ", "text")]},
    {"id": "select", "label": "Chọn nội dung", "icon": "🧠", "x": 480, "y": 160, "job": "select", "states": ["selecting"],
     "desc": "Claude headless chạy skill chọn nội dung JRE, ra cutlist.",
     "fields": [("claude_model_select", "Model", MODELS), ("claude_effort_select", "Effort", EFFORTS),
                ("max_segments", "Số đoạn tối đa", "number"), ("select_retry", "Số lần thử lại", "number"),
                ("claude_fallback_model", "Model dự phòng", "text")]},
    {"id": "review", "label": "Duyệt cutlist", "icon": "✋", "x": 700, "y": 160, "job": None, "states": ["reviewing"],
     "gate": "review_gate", "desc": "Cổng duyệt tay trước khi cắt. Tắt thì đi thẳng sang cắt.",
     "fields": [("review_gate", "Bật cổng duyệt", "bool")]},
    {"id": "cut", "label": "Cắt clip", "icon": "✂️", "x": 920, "y": 160, "job": "cut", "states": ["selected", "cutting"],
     "desc": "Video Cutter cắt các đoạn trong cutlist.",
     "fields": []},
    {"id": "zoom", "label": "Zoom", "icon": "🔍", "x": 1140, "y": 60, "job": "zoom", "states": ["zooming"],
     "gate": "auto_zoom", "desc": "Podcast Zoom bám người đang nói. Tắt tự động thì chỉ zoom đoạn bạn chọn.",
     "fields": [("auto_zoom", "Tự zoom sau khi cắt", "bool"), ("zoom_hooks", "Zoom cả hook", "bool"),
                ("zoom_factor", "Hệ số zoom", "number"), ("zoom_smoothing_speed", "Độ mượt", "number"),
                ("zoom_max_faces", "Số mặt tối đa", "number"),
                ("delete_original_clip_after_zoom", "Xoá clip gốc sau khi zoom", "bool")]},
    {"id": "index", "label": "Lập chỉ mục", "icon": "🗂️", "x": 1140, "y": 260, "job": "index", "states": ["indexing"],
     "desc": "Đưa đoạn vào kho highlight để tìm kiếm.", "fields": []},
    {"id": "ready", "label": "Kho highlight", "icon": "✅", "x": 1360, "y": 160, "job": None, "states": ["ready"],
     "desc": "Tập đã xong toàn bộ.",
     "fields": [("delete_source_after_ready", "Xoá video gốc khi xong", "bool"), ("disk_warn_gb", "Cảnh báo ổ đĩa (GB)", "number")]},
    # Branches started by hand from the episode / compile pages
    {"id": "title", "label": "Title & thumbnail", "icon": "🏷️", "x": 1360, "y": 380, "job": "title", "states": [], "branch": True,
     "desc": "Nút Viết Title trên từng đoạn.",
     "fields": [("title_skill", "Skill", "text"), ("claude_model_title", "Model", "text"),
                ("claude_effort_title", "Effort", EFFORTS), ("thumb_image_model", "Model ảnh thumbnail", "text"),
                ("thumb_image_quality", "Chất lượng ảnh", ["low", "medium", "high"])]},
    {"id": "hookjoin", "label": "Nối hook", "icon": "🔗", "x": 1580, "y": 380, "job": "hookjoin", "states": [], "branch": True,
     "desc": "Ghép hook với đoạn highlight đã zoom.",
     "fields": [("hook_join_transition", "Hiệu ứng chuyển", "text"), ("hook_join_duration", "Thời lượng (giây)", "number"),
                ("hook_join_sfx_volume", "Âm lượng SFX", "number")]},
    {"id": "compile", "label": "Video tổng hợp", "icon": "🎞️", "x": 1580, "y": 60, "job": None, "states": [], "branch": True,
     "table": "compile_jobs", "desc": "Gộp nhiều tập theo một chủ đề, có lời dẫn.",
     "fields": [("claude_model_compile_scan", "Model quét", MODELS), ("claude_effort_compile_scan", "Effort quét", EFFORTS),
                ("claude_model_compile_arc", "Model dựng mạch", MODELS), ("claude_effort_compile_arc", "Effort dựng mạch", EFFORTS),
                ("compile_max_scan_tokens", "Ngân sách token quét", "number"),
                ("compile_require_zoom", "Bắt buộc clip đã zoom", "bool")]},
    {"id": "docext", "label": "Phim tài liệu", "icon": "📽️", "x": 1580, "y": 220, "job": None, "states": [], "branch": True,
     "table": "docext_jobs", "desc": "Creater Vid làm phim tài liệu nối tiếp đoạn highlight.",
     "fields": [("docext_target_min", "Độ dài mặc định (phút)", "number"), ("docext_budget_usd", "Ngân sách (USD)", "text")]},
]

EDGES = [("intake", "transcribe"), ("transcribe", "select"), ("select", "review"), ("review", "cut"),
         ("cut", "zoom"), ("cut", "index"), ("zoom", "index"), ("index", "ready"),
         ("ready", "title"), ("title", "hookjoin"), ("ready", "compile"), ("ready", "docext")]

# Stage of the orchestrator a node maps to, for "Chạy lại từ bước này".
RUN_FROM = {"transcribe": "transcribe", "select": "select", "cut": "cut", "zoom": "zoom", "index": "index"}

EDITABLE = {f[0] for n in NODES for f in n["fields"]}

# Source files behind each node, handed to Claude in the dev chat (paths relative to the app folder).
FILES = {
    "intake": ["studio/pipeline/intake.py", "studio/pipeline/orchestrator.py (intake_file, intake_url)", "studio/ingest.py",
               "templates/queue.html"],
    "transcribe": ["studio/pipeline/transcribe.py", "studio/pipeline/orchestrator.py (_stage_transcribe)"],
    "select": ["studio/pipeline/select_ai.py", "studio/pipeline/claude_runner.py", "studio/pipeline/validator.py",
               ".claude/skills/chon-noi-dung-jre-v2/ (skill Claude chạy để chọn nội dung)",
               "studio/pipeline/orchestrator.py (_stage_select)"],
    "review": ["studio/pipeline/orchestrator.py (approve, review_gate)", "templates/episode.html"],
    "cut": ["studio/pipeline/cut.py (gọi Video Cutter ở C:/Tool/video-cutter-portable)", "studio/pipeline/orchestrator.py (_stage_cut)"],
    "zoom": ["studio/pipeline/zoom.py (gọi Podcast Zoom ở C:/Tool/podcast-zoom-tool)",
             "studio/pipeline/orchestrator.py (enqueue_zoom, run_zoom, _stage_zoom)"],
    "index": ["studio/search.py", "studio/ingest.py", "studio/tagging.py", "studio/pipeline/orchestrator.py (_stage_index)"],
    "ready": ["studio/pipeline/orchestrator.py (_delete_source)", "studio/maintenance.py", "templates/episodes.html"],
    "title": ["studio/pipeline/titles.py", "studio/pipeline/gemini_runner.py", ".claude/skills/viet-tittle/",
              "templates/_title_block.html", "templates/_thumb_block.html"],
    "hookjoin": ["studio/pipeline/hook_join.py", "studio/pipeline/hook_recut.py"],
    "compile": ["studio/pipeline/compile_video.py", "studio/pipeline/topic_scan.py", "templates/compile.html",
                "templates/compile_job.html", "templates/compilations.html"],
    "docext": ["studio/pipeline/doc_extend.py (gọi Creater Vid ở C:/Tool/Creater Vid)"],
}
GRAPH_FILES = "studio/flow.py (NODES, EDGES, FILES), templates/pipeline.html, static/devchat.js, app.py (route /pipeline)"


def dev_context(node_id: str) -> dict | None:
    """What the dev chat tells Claude about a node ("_all" = the whole pipeline)."""
    if node_id == "_all":
        return {"label": "Toàn bộ pipeline", "desc": "Cả luồng: " + " → ".join(n["label"] for n in NODES if not n.get("branch"))
                + "; nhánh tay: " + ", ".join(n["label"] for n in NODES if n.get("branch")) + ".",
                "files": ["app.py", "studio/pipeline/orchestrator.py", "studio/config.py (DEFAULT_SETTINGS)",
                          "studio/schema.sql", "README.md", "PLAN.md"],
                "settings": [], "graph_files": GRAPH_FILES}
    n = next((x for x in NODES if x["id"] == node_id), None)
    if not n:
        return None
    return {"label": n["label"], "desc": n["desc"], "files": FILES.get(node_id, []),
            "settings": [f[0] for f in n["fields"]], "graph_files": GRAPH_FILES,
            "extra": "Thứ tự bước tự động: studio/pipeline/orchestrator.py (STAGES). Cài đặt mặc định: studio/config.py."}


def _job_stats(stage: str) -> dict:
    s = db.row(
        """SELECT SUM(status='done') AS done, SUM(status='failed') AS failed, SUM(status='skipped') AS skipped,
                  SUM(status='running') AS running,
                  AVG(CASE WHEN status='done' AND finished_at IS NOT NULL
                           THEN (julianday(finished_at) - julianday(started_at)) * 86400 END) AS avg_sec
           FROM (SELECT * FROM jobs WHERE stage=? ORDER BY id DESC LIMIT 200)""", (stage,)) or {}
    running = db.rows("SELECT id, episode_id, progress, message, started_at FROM jobs "
                      "WHERE stage=? AND status='running' ORDER BY id DESC LIMIT 5", (stage,))
    last_err = db.row("SELECT episode_id, error, finished_at FROM jobs WHERE stage=? AND status='failed' "
                      "ORDER BY id DESC LIMIT 1", (stage,))
    return {k: (s.get(k) or 0) for k in ("done", "failed", "skipped", "running")} | {
        "avg_sec": round(s["avg_sec"]) if s.get("avg_sec") else None, "active": running, "last_error": last_err}


def _table_stats(table: str) -> dict:
    by = {r["status"] or "?": r["n"] for r in db.rows(f"SELECT status, COUNT(*) AS n FROM {table} GROUP BY status")}
    busy = sum(n for st, n in by.items() if st not in ("done", "failed", "review", "stopped", "cancelled"))
    return {"done": by.get("done", 0), "failed": by.get("failed", 0), "skipped": 0, "running": busy,
            "avg_sec": None, "active": [], "last_error": None, "by_status": by}


def graph(pipe: dict | None) -> dict:
    """Everything the page draws, recomputed on every poll (a handful of small queries)."""
    pipe = pipe or {"current": None, "queue": []}
    settings = db.all_settings()
    eps = db.rows("SELECT id, guest, stage, stage_error, updated_at FROM episodes ORDER BY updated_at DESC")
    nodes = []
    for n in NODES:
        stats = _table_stats(n["table"]) if n.get("table") else _job_stats(n["job"]) if n.get("job") else \
            {"done": 0, "failed": 0, "skipped": 0, "running": 0, "avg_sec": None, "active": [], "last_error": None}
        here = [e for e in eps if (e["stage"] or "new") in n["states"]]
        failed_here = [e for e in eps if n["id"] in RUN_FROM and (e["stage"] or "") == f"failed:{n['id']}"]
        if n["id"] == "intake":
            failed_here = [e for e in eps if (e["stage"] or "") in ("failed:download", "failed:unknown")]
        gate = n.get("gate")
        nodes.append({
            "id": n["id"], "label": n["label"], "icon": n["icon"], "x": n["x"], "y": n["y"], "desc": n["desc"],
            "branch": bool(n.get("branch")), "run_from": RUN_FROM.get(n["id"]),
            "enabled": (str(settings.get(gate, "0")) == "1") if gate else True,
            "episodes": here if n["id"] != "ready" else here[:30], "n_here": len(here), "failed_eps": failed_here,
            "stats": stats,
            "fields": [{"key": k, "label": lbl, "kind": kind, "value": settings.get(k, config.DEFAULT_SETTINGS.get(k, ""))}
                       for k, lbl, kind in n["fields"]],
        })
    return {"nodes": nodes, "edges": [{"from": a, "to": b} for a, b in EDGES], "pipe": pipe,
            "worker": pipe is not None}


def save_settings(values: dict) -> dict:
    """Only keys a node exposes: the page can never write arbitrary settings."""
    saved = {}
    for k, v in (values or {}).items():
        if k in EDITABLE:
            db.set_setting(k, ("1" if v else "0") if isinstance(v, bool) else str(v).strip())
            saved[k] = db.get_setting(k)
    return {"saved": saved, "rejected": sorted(set(values or {}) - EDITABLE)}
