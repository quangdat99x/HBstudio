#!/usr/bin/env python
"""hldb: command line access to the JRE Studio highlight database (used by the /kho-highlight skill).

Examples:
  hldb init
  hldb scan                              # scan the media root (cutlists, videos, clip folders)
  hldb ingest "E:/.../cutlist_JRE-2530.json"
  hldb search "kandahar giant" --min-intensity 8 --unused --json
  hldb show JRE-2530#3
  hldb episodes | topics | stats
  hldb export --ids 12 15 18 --format pool --out pool.json
  hldb import-analysis JRE-2556 analysis.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from studio import db  # noqa: E402
from studio import export as export_mod  # noqa: E402
from studio import ingest, search  # noqa: E402
from studio.analysis import import_analysis_json, import_markdown  # noqa: E402


def _print(obj, as_json: bool):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    else:
        if isinstance(obj, list):
            for it in obj:
                print(_fmt_row(it) if isinstance(it, dict) else it)
        elif isinstance(obj, dict):
            print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
        else:
            print(obj)


def _fmt_row(r: dict) -> str:
    if "start_hms" in r:
        tag = "H" if r.get("kind") == "hook" else " "
        return (f"[{r['id']:>4}] {tag} {r['episode_id']:<11} #{r.get('rank') or '-':<3} {r['start_hms']}-{r['end_hms']} "
                f"i{r.get('intensity') or '-'} s{r.get('final_score') or '-'} {r.get('status','')[:6]:<6} {r['title'][:70]}")
    return json.dumps(r, ensure_ascii=False, default=str)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hldb")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database")
    p = sub.add_parser("scan", help="scan media root"); p.add_argument("root", nargs="?"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("ingest", help="ingest one cutlist"); p.add_argument("path"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("reindex", help="rebuild the search index")

    p = sub.add_parser("search", help="search segments")
    p.add_argument("q", nargs="?", default="")
    p.add_argument("--episode"); p.add_argument("--podcast"); p.add_argument("--guest"); p.add_argument("--kind")
    p.add_argument("--min-intensity", type=float); p.add_argument("--min-gtf", type=float); p.add_argument("--min-score", type=float)
    p.add_argument("--reach"); p.add_argument("--status"); p.add_argument("--theme"); p.add_argument("--topic")
    p.add_argument("--unused", action="store_true"); p.add_argument("--limit", type=int, default=30); p.add_argument("--offset", type=int, default=0)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("show", help="show one segment (id or EP#rank)"); p.add_argument("ref"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("episodes", help="list episodes"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("episode", help="show one episode with its segments"); p.add_argument("episode_id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("topics", help="list topics by frequency"); p.add_argument("--top", type=int, default=50); p.add_argument("--json", action="store_true")
    p = sub.add_parser("themes", help="list themes"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("stats", help="counts"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("suggest-compilations", help="topics with >=4 segments from >=2 episodes"); p.add_argument("--json", action="store_true")

    p = sub.add_parser("export", help="export selected segments")
    p.add_argument("--ids", nargs="+", required=True); p.add_argument("--format", choices=["pool", "multi"], default="pool")
    p.add_argument("--theme", default=""); p.add_argument("--out", required=True)

    p = sub.add_parser("mark", help="update status/paths of a segment")
    p.add_argument("ref"); p.add_argument("--status"); p.add_argument("--clip"); p.add_argument("--zoomed"); p.add_argument("--url")

    p = sub.add_parser("import-analysis", help="attach skill analysis blocks (markdown or json) to segments")
    p.add_argument("episode_id"); p.add_argument("path"); p.add_argument("--source", default="manual")

    p = sub.add_parser("tag", help="themes/entities: --pending prints segments lacking themes; --apply <json> writes them")
    p.add_argument("--pending", action="store_true"); p.add_argument("--apply"); p.add_argument("--limit", type=int, default=40)

    args = ap.parse_args(argv)
    db.init_db()
    as_json = getattr(args, "json", False)

    if args.cmd == "init":
        print(f"ok: {db.config.DB_PATH}")
    elif args.cmd == "scan":
        _print(ingest.scan_media_root(Path(args.root) if args.root else None, force=args.force), True)
    elif args.cmd == "ingest":
        _print(ingest.ingest_cutlist(Path(args.path), force=args.force), True)
        search.rebuild_index()
    elif args.cmd == "reindex":
        print(f"reindexed {search.rebuild_index()} segments")
    elif args.cmd == "search":
        res = search.search(args.q, episode_id=args.episode, podcast_id=args.podcast, guest=args.guest, kind=args.kind,
                            min_intensity=args.min_intensity, min_gtf=args.min_gtf, min_score=args.min_score,
                            keyword_reach=args.reach, status=args.status, theme=args.theme, topic=args.topic,
                            unused=args.unused, limit=args.limit, offset=args.offset)
        _print(res, as_json)
    elif args.cmd == "show":
        sid = search.resolve_segment_ref(args.ref)
        d = search.segment_detail(sid) if sid else None
        if not d:
            print(f"not found: {args.ref}"); return 1
        if as_json:
            _print(d, True)
        else:
            for k in ("id", "episode_id", "guest", "kind", "rank", "content_rank", "start_hms", "end_hms", "duration_sec",
                      "title", "summary_vi", "summary_en", "hook_en", "intensity", "cq", "gtf", "final_score", "value_axis",
                      "core_keyword", "keyword_reach", "keyword_credibility", "keyword_reason", "fit_reason", "status",
                      "clip_path", "clip_zoomed_path", "topics", "themes", "entities", "hooks", "compilations"):
                if d.get(k) not in (None, "", [], {}):
                    print(f"{k}: {d[k]}")
            if d.get("analysis_md"):
                print("\n--- analysis ---\n" + d["analysis_md"])
    elif args.cmd == "episodes":
        _print(db.rows("SELECT e.id, e.guest, e.stage, e.source_video, "
                       "(SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='highlight') AS highlights, "
                       "(SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.kind='hook') AS hooks, "
                       "(SELECT COUNT(*) FROM segments s WHERE s.episode_id=e.id AND s.clip_zoomed_path IS NOT NULL) AS zoomed "
                       "FROM episodes e ORDER BY e.podcast_id, e.number DESC"), as_json)
    elif args.cmd == "episode":
        ep = db.row("SELECT * FROM episodes WHERE id=?", (args.episode_id.upper(),))
        if not ep:
            print("not found"); return 1
        segs = search.search("", episode_id=ep["id"], limit=500)
        if as_json:
            _print({"episode": ep, "segments": segs}, True)
        else:
            print(json.dumps({k: v for k, v in ep.items() if k not in ("guest_profile_json", "selection_log_md")},
                             ensure_ascii=False, indent=2))
            _print(segs, False)
    elif args.cmd == "topics":
        _print(db.rows("SELECT t.name, COUNT(*) AS n, COUNT(DISTINCT s.episode_id) AS episodes FROM topics t "
                       "JOIN segment_topics st ON st.topic_id=t.id JOIN segments s ON s.id=st.segment_id "
                       "GROUP BY t.id ORDER BY n DESC, t.name LIMIT ?", (args.top,)), as_json)
    elif args.cmd == "themes":
        _print(db.rows("SELECT th.slug, th.name_vi, COUNT(st.segment_id) AS n FROM themes th "
                       "LEFT JOIN segment_themes st ON st.theme_id=th.id GROUP BY th.id ORDER BY n DESC"), as_json)
    elif args.cmd == "stats":
        _print({
            "episodes": db.scalar("SELECT COUNT(*) FROM episodes"),
            "highlights": db.scalar("SELECT COUNT(*) FROM segments WHERE kind='highlight'"),
            "hooks": db.scalar("SELECT COUNT(*) FROM segments WHERE kind='hook'"),
            "with_clip": db.scalar("SELECT COUNT(*) FROM segments WHERE clip_path IS NOT NULL"),
            "zoomed": db.scalar("SELECT COUNT(*) FROM segments WHERE clip_zoomed_path IS NOT NULL"),
            "with_analysis": db.scalar("SELECT COUNT(*) FROM segments WHERE analysis_md IS NOT NULL"),
            "topics": db.scalar("SELECT COUNT(*) FROM topics"),
            "themes": db.scalar("SELECT COUNT(*) FROM themes"),
            "transcript_lines": db.scalar("SELECT COUNT(*) FROM transcript_lines"),
            "by_status": {r["status"]: r["n"] for r in db.rows("SELECT status, COUNT(*) n FROM segments GROUP BY status")},
            "by_stage": {r["stage"]: r["n"] for r in db.rows("SELECT stage, COUNT(*) n FROM episodes GROUP BY stage")},
        }, True)
    elif args.cmd == "suggest-compilations":
        by_theme = db.rows(
            "SELECT th.slug AS theme, th.name_vi, COUNT(*) AS segments, COUNT(DISTINCT s.episode_id) AS episodes, "
            "ROUND(SUM(s.duration_sec)/60.0,1) AS minutes, group_concat(DISTINCT s.episode_id) AS episode_ids "
            "FROM themes th JOIN segment_themes st ON st.theme_id=th.id JOIN segments s ON s.id=st.segment_id "
            "WHERE s.kind='highlight' AND s.id NOT IN (SELECT segment_id FROM compilation_items) "
            "GROUP BY th.id HAVING segments>=4 AND episodes>=2 ORDER BY episodes DESC, segments DESC")
        by_topic = db.rows(
            "SELECT t.name AS topic, COUNT(*) AS segments, COUNT(DISTINCT s.episode_id) AS episodes, "
            "ROUND(SUM(s.duration_sec)/60.0,1) AS minutes FROM topics t JOIN segment_topics st ON st.topic_id=t.id "
            "JOIN segments s ON s.id=st.segment_id WHERE s.kind='highlight' "
            "AND s.id NOT IN (SELECT segment_id FROM compilation_items) "
            "GROUP BY t.id HAVING segments>=4 AND episodes>=2 ORDER BY episodes DESC, segments DESC")
        _print({"by_theme": by_theme, "by_topic": by_topic}, True)
    elif args.cmd == "export":
        ids = [search.resolve_segment_ref(r) for r in args.ids]
        ids = [i for i in ids if i]
        out = export_mod.export_segments(ids, fmt=args.format, theme=args.theme, out_path=Path(args.out))
        print(f"ok: {out}")
    elif args.cmd == "mark":
        sid = search.resolve_segment_ref(args.ref)
        if not sid:
            print("not found"); return 1
        sets, params = [], []
        for col, val in (("status", args.status), ("clip_path", args.clip), ("clip_zoomed_path", args.zoomed)):
            if val:
                sets.append(f"{col}=?"); params.append(val)
        if sets:
            with db.tx() as c:
                c.execute(f"UPDATE segments SET {', '.join(sets)} WHERE id=?", params + [sid])
        if args.url:
            with db.tx() as c:
                c.execute("INSERT INTO publications(segment_id, url, updated_at) VALUES(?,?,datetime('now'))", (sid, args.url))
        print("ok")
    elif args.cmd == "import-analysis":
        p = Path(args.path)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() == ".json":
            _print(import_analysis_json(args.episode_id.upper(), json.loads(text), source=args.source), True)
        else:
            _print(import_markdown(args.episode_id.upper(), text, source=args.source), True)
    elif args.cmd == "tag":
        from studio import tagging
        if args.apply:
            _print(tagging.apply_tags(json.loads(Path(args.apply).read_text(encoding="utf-8"))), True)
        else:
            _print(tagging.pending(limit=args.limit), True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
