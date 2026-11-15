-- Hổ Báo Studio database schema (SQLite + FTS5)
-- Idempotent: every statement uses IF NOT EXISTS so it can run at every startup.

CREATE TABLE IF NOT EXISTS podcasts (
  id      TEXT PRIMARY KEY,          -- 'JRE', 'JREMMA'
  name    TEXT NOT NULL,
  host    TEXT
);
INSERT OR IGNORE INTO podcasts (id, name, host) VALUES
  ('JRE',    'Joe Rogan Experience', 'Joe Rogan'),
  ('JREMMA', 'JRE MMA Show',         'Joe Rogan');

CREATE TABLE IF NOT EXISTS episodes (
  id                 TEXT PRIMARY KEY,   -- 'JRE-2530', 'JREMMA-183'
  podcast_id         TEXT NOT NULL REFERENCES podcasts(id),
  number             INTEGER,
  guest              TEXT,
  title              TEXT,
  source_video       TEXT,               -- video file name as Video Cutter expects it
  video_path         TEXT,               -- absolute path when found on disk
  transcript_path    TEXT,
  clip_folder        TEXT,               -- folder holding the cut clips
  duration_sec       REAL,
  guest_profile_json TEXT,               -- Guest Card from the cutlist
  guest_card_md      TEXT,               -- Guest Card as printed by the skill
  selection_log_md   TEXT,               -- full text of the headless selection run
  cutlist_path       TEXT,
  stage              TEXT NOT NULL DEFAULT 'new',   -- pipeline state machine
  stage_error        TEXT,
  aired_on           TEXT,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
  id                      INTEGER PRIMARY KEY,
  episode_id              TEXT NOT NULL REFERENCES episodes(id),
  kind                    TEXT NOT NULL DEFAULT 'highlight',   -- 'highlight' | 'hook'
  parent_id               INTEGER REFERENCES segments(id),     -- hook -> parent highlight
  start_sec               REAL,          -- NULL only for backfilled clips whose timestamps are unknown
  end_sec                 REAL,
  start_hms               TEXT,
  end_hms                 TEXT,
  duration_sec            REAL,
  title                   TEXT NOT NULL,
  summary_vi              TEXT,
  summary_en              TEXT,
  hook_en                 TEXT,
  quote_en                TEXT,
  hook_type               TEXT,
  intensity               INTEGER,
  cq                      REAL,
  gtf                     REAL,
  final_score             REAL,
  value_axis              TEXT,
  content_type            TEXT,
  core_keyword            TEXT,
  keyword_reach           TEXT,
  keyword_credibility     TEXT,
  keyword_reason          TEXT,
  satellite_keywords_json TEXT,
  fit_reason              TEXT,
  rank                    INTEGER,       -- cut order in the latest cutlist (= NN prefix of the clip file)
  content_rank            INTEGER,       -- quality rank, 1 = best
  status                  TEXT NOT NULL DEFAULT 'selected',   -- selected|cut|zoomed|ready|published|archived
  clip_path               TEXT,
  clip_zoomed_path        TEXT,
  thumbnail_path          TEXT,
  transcript              TEXT,          -- transcript slice of this segment
  analysis_md             TEXT,          -- the skill's full analysis block for this segment (Mục VI)
  analysis_json           TEXT,          -- structured analysis (tom_tat, ly_do_dat, keyword, fit, ...)
  source_skill            TEXT,
  cutlist_version         TEXT,
  cutlist_path            TEXT,
  last_seen               TEXT,
  extra_json              TEXT,
  raw_json                TEXT,
  created_at              TEXT NOT NULL,
  updated_at              TEXT NOT NULL,
  UNIQUE (episode_id, kind, start_sec, end_sec)
);
CREATE INDEX IF NOT EXISTS idx_segments_episode ON segments(episode_id);
CREATE INDEX IF NOT EXISTS idx_segments_status  ON segments(status);
CREATE INDEX IF NOT EXISTS idx_segments_kind    ON segments(kind);

-- raw topics written by the skill (many-to-many)
CREATE TABLE IF NOT EXISTS topics (
  id        INTEGER PRIMARY KEY,
  name      TEXT UNIQUE,
  name_norm TEXT
);
CREATE TABLE IF NOT EXISTS segment_topics (
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  topic_id   INTEGER NOT NULL REFERENCES topics(id),
  PRIMARY KEY (segment_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_segment_topics_topic ON segment_topics(topic_id);

-- controlled taxonomy, assigned by Claude at index time
CREATE TABLE IF NOT EXISTS themes (
  id        INTEGER PRIMARY KEY,
  slug      TEXT UNIQUE,
  name_vi   TEXT,
  parent_id INTEGER
);
CREATE TABLE IF NOT EXISTS segment_themes (
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  theme_id   INTEGER NOT NULL REFERENCES themes(id),
  is_primary INTEGER DEFAULT 0,
  confidence REAL,
  PRIMARY KEY (segment_id, theme_id)
);

-- named entities: person / place / org / work / event
CREATE TABLE IF NOT EXISTS entities (
  id   INTEGER PRIMARY KEY,
  name TEXT,
  type TEXT,
  UNIQUE (name, type)
);
CREATE TABLE IF NOT EXISTS segment_entities (
  segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  entity_id  INTEGER NOT NULL REFERENCES entities(id),
  PRIMARY KEY (segment_id, entity_id)
);

-- full episode transcript (Whisper segments)
CREATE TABLE IF NOT EXISTS transcript_lines (
  episode_id TEXT NOT NULL REFERENCES episodes(id),
  seq        INTEGER NOT NULL,
  start_sec  REAL NOT NULL,
  end_sec    REAL NOT NULL,
  text       TEXT NOT NULL,
  PRIMARY KEY (episode_id, seq)
);

-- flat search buffer + FTS5 external-content index
CREATE TABLE IF NOT EXISTS segment_search (
  segment_id   INTEGER PRIMARY KEY,
  title        TEXT, summary_en TEXT, summary_vi TEXT, hook_en TEXT, quote_en TEXT,
  topics_text  TEXT, core_keyword TEXT, guest TEXT, entities_text TEXT, themes_text TEXT,
  analysis     TEXT, transcript TEXT, ascii_text TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
  title, summary_en, summary_vi, hook_en, quote_en,
  topics_text, core_keyword, guest, entities_text, themes_text,
  analysis, transcript, ascii_text,
  content='segment_search', content_rowid='segment_id',
  tokenize='unicode61 remove_diacritics 2'
);

-- compilations (rabbit hole) and publications
CREATE TABLE IF NOT EXISTS compilations (
  id            INTEGER PRIMARY KEY,
  theme         TEXT,
  slug          TEXT UNIQUE,
  manifest_path TEXT,
  cutlist_path  TEXT,
  status        TEXT,
  created_at    TEXT
);
CREATE TABLE IF NOT EXISTS compilation_items (
  compilation_id INTEGER NOT NULL REFERENCES compilations(id) ON DELETE CASCADE,
  segment_id     INTEGER NOT NULL REFERENCES segments(id),
  ord            INTEGER,
  role           TEXT,
  PRIMARY KEY (compilation_id, segment_id)
);
CREATE TABLE IF NOT EXISTS publications (
  id             INTEGER PRIMARY KEY,
  segment_id     INTEGER,
  compilation_id INTEGER,
  youtube_id     TEXT,
  url            TEXT,
  yt_title       TEXT,
  published_at   TEXT,
  views          INTEGER,
  stats_json     TEXT,
  updated_at     TEXT
);

-- title & metadata runs (skill viet-tittle) for one highlight; every run is kept, the page shows the latest
CREATE TABLE IF NOT EXISTS segment_titles (
  id                INTEGER PRIMARY KEY,
  segment_id        INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
  skill             TEXT,
  model             TEXT,
  effort            TEXT,
  status            TEXT NOT NULL,        -- queued | running | done | failed
  progress_msg      TEXT,
  output_md         TEXT,                 -- the skill's full answer
  output_json       TEXT,                 -- structured fields written by the run
  recommended_title TEXT,
  error             TEXT,
  models_used       TEXT,
  usage_json        TEXT,
  duration_sec      REAL,
  created_at        TEXT NOT NULL,
  started_at        TEXT,
  finished_at       TEXT,
  session_id        TEXT,                 -- Claude Code session of this run; a chat turn resumes it
  parent_id         INTEGER,              -- chat turn: the run whose metadata it adjusts (NULL = fresh "Viết Title")
  user_message      TEXT,                 -- chat turn: what the user asked Claude to change
  session_cost_usd  REAL,                 -- total_cost_usd reported by the CLI (cumulative over a resumed session)
  focus             TEXT,                 -- user's focus for this run: metadata + HOOK 01 built around it, not core_keyword
  kind              TEXT                  -- NULL/'title' = Viết Title; 'thumb' = a thumbnail version (own folder thumb_NN\v<id>)
);
CREATE INDEX IF NOT EXISTS idx_segment_titles_segment ON segment_titles(segment_id);

-- guests grouped by what JRE listeners come to hear them on (studio/guests.py)
CREATE TABLE IF NOT EXISTS guest_groups (
  slug        TEXT PRIMARY KEY,
  name_vi     TEXT NOT NULL,
  hint        TEXT,                        -- who belongs here (page + Claude's classification prompt)
  sort        INTEGER DEFAULT 100
);
CREATE TABLE IF NOT EXISTS guests (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  name_norm   TEXT NOT NULL UNIQUE,        -- episodes link by norm_key(episodes.guest), "A & B" = two guests
  group_slug  TEXT,                        -- main group
  also_json   TEXT,                        -- secondary groups ["slug", ...] (0-2)
  expertise   TEXT,                        -- one line: what listeners come to hear them on
  source      TEXT,                        -- claude | manual (manual is never overwritten)
  updated_at  TEXT
);

-- pipeline
CREATE TABLE IF NOT EXISTS jobs (
  id          INTEGER PRIMARY KEY,
  episode_id  TEXT NOT NULL,
  stage       TEXT NOT NULL,          -- transcribe | select | cut | zoom | index | download
  status      TEXT NOT NULL,          -- queued | running | done | failed | skipped
  progress    REAL DEFAULT 0,
  message     TEXT,
  attempts    INTEGER DEFAULT 0,
  started_at  TEXT,
  finished_at TEXT,
  error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_episode ON jobs(episode_id);
CREATE TABLE IF NOT EXISTS job_events (
  id      INTEGER PRIMARY KEY,
  job_id  INTEGER,
  ts      TEXT,
  level   TEXT,
  message TEXT
);
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS ingest_log (
  id          INTEGER PRIMARY KEY,
  path        TEXT,
  sha1        TEXT,
  kind        TEXT,
  result      TEXT,
  ingested_at TEXT
);

-- Topic compilations scanned from FULL episode transcripts (studio/pipeline/topic_scan.py)
CREATE TABLE IF NOT EXISTS topic_scans (
  id           INTEGER PRIMARY KEY,
  topic        TEXT NOT NULL,
  keywords     TEXT,
  pad_sec      REAL,
  episode_ids  TEXT,               -- comma list, empty = every episode with a transcript
  model        TEXT,
  effort       TEXT,
  status       TEXT,               -- queued | running | done | failed | cutting
  n_episodes   INTEGER,
  n_windows    INTEGER,
  est_tokens   INTEGER,
  usage_json   TEXT,
  cost_usd     REAL,
  summary      TEXT,
  error        TEXT,
  cutlist_path TEXT,
  out_dir      TEXT,
  created_at   TEXT,
  updated_at   TEXT
);
CREATE TABLE IF NOT EXISTS topic_scan_items (
  id            INTEGER PRIMARY KEY,
  scan_id       INTEGER NOT NULL REFERENCES topic_scans(id),
  ord           INTEGER,
  episode_id    TEXT,
  start_sec     REAL,
  end_sec       REAL,
  title         TEXT,
  summary_vi    TEXT,
  reason_vi     TEXT,
  score         REAL,
  included      INTEGER NOT NULL DEFAULT 1,
  source_kind   TEXT,              -- full | clip | missing
  source_path   TEXT,
  source_offset REAL,
  clip_path     TEXT
);
CREATE INDEX IF NOT EXISTS idx_topic_items_scan ON topic_scan_items(scan_id);

-- Video tổng hợp (studio/pipeline/compile_video.py): one highlight picked by the user opens a long compilation
CREATE TABLE IF NOT EXISTS compile_jobs (
  id               INTEGER PRIMARY KEY,
  seed_segment_id  INTEGER NOT NULL REFERENCES segments(id),
  target_min       INTEGER NOT NULL,       -- length the user asked for (30, 60, 90 ...)
  note             TEXT,                   -- the user's wishes for this video
  topic_en         TEXT,
  topic_vi         TEXT,
  angle_vi         TEXT,                   -- the big question the arc follows
  keywords         TEXT,                   -- filter keywords for the full-transcript scan
  status           TEXT,                   -- queued | topic | scanning | arranging | review | building | done | failed
  progress_msg     TEXT,
  error            TEXT,
  n_episodes       INTEGER,
  n_windows        INTEGER,
  est_tokens       INTEGER,
  n_candidates     INTEGER,
  title_en         TEXT,
  intro_text       TEXT,                   -- ElevenLabs v3 prompt played right after the seed clip
  outro_text       TEXT,
  arc_note         TEXT,
  cost_usd         REAL DEFAULT 0,         -- Claude cost (ElevenLabs is in Creater's quota bar)
  out_dir          TEXT,
  final_path       TEXT,
  final_sec        REAL,
  created_at       TEXT,
  updated_at       TEXT
);
CREATE TABLE IF NOT EXISTS compile_candidates (
  id            INTEGER PRIMARY KEY,
  job_id        INTEGER NOT NULL REFERENCES compile_jobs(id),
  episode_id    TEXT,
  start_sec     REAL,
  end_sec       REAL,
  title         TEXT,
  summary_vi    TEXT,
  point_en      TEXT,
  ends_en       TEXT,
  score         REAL,
  source_kind   TEXT,              -- full | clip
  source_path   TEXT,
  source_offset REAL
);
CREATE INDEX IF NOT EXISTS idx_compile_cand_job ON compile_candidates(job_id);
CREATE TABLE IF NOT EXISTS compile_items (
  id            INTEGER PRIMARY KEY,
  job_id        INTEGER NOT NULL REFERENCES compile_jobs(id),
  ord           INTEGER,
  kind          TEXT,              -- seed | clip
  role          TEXT,              -- cold_open | setup | deepening | twist | dialectic | revelation | added
  cand_id       INTEGER,
  episode_id    TEXT,
  start_sec     REAL,
  end_sec       REAL,
  title         TEXT,
  summary_vi    TEXT,
  why_vi        TEXT,
  bridge_text   TEXT,              -- ElevenLabs v3 prompt played after this clip (NULL on the last clip)
  included      INTEGER NOT NULL DEFAULT 1,
  source_kind   TEXT,
  source_path   TEXT,
  source_offset REAL
);
CREATE INDEX IF NOT EXISTS idx_compile_items_job ON compile_items(job_id);

-- Phim tài liệu bổ sung (studio/pipeline/doc_extend.py): highlight + hook đã nối → Creater Vid làm phim dossier →
-- nối: [highlight+hook, giữ nguyên nội dung] + [câu nối ElevenLabs] + [phim tài liệu] → <stem>_DOC.mp4
CREATE TABLE IF NOT EXISTS docext_jobs (
  id            INTEGER PRIMARY KEY,
  segment_id    INTEGER NOT NULL REFERENCES segments(id),
  hooked_path   TEXT NOT NULL,           -- the highlight + hook file (never modified)
  target_min    INTEGER NOT NULL,        -- documentary length the user asked for (approximate)
  note          TEXT,                    -- the user's wishes for the documentary
  budget_usd    REAL,                    -- Creater asset budget (images, voice)
  auto_advance  INTEGER DEFAULT 1,       -- 1 = Creater runs every step by itself
  use_jre       INTEGER DEFAULT 0,       -- 1 = Creater may use the JRE highlight archive
  creater_pid   INTEGER,                 -- the Creater Vid project
  creater_dir   TEXT,
  status        TEXT,                    -- creating | filming | joining | done | failed | stopped
  progress_msg  TEXT,
  error         TEXT,
  doc_path      TEXT,                    -- the approved Creater render used for the join
  bridge_text   TEXT,                    -- ElevenLabs v3 prompt of the one bridging line
  bridge_user   INTEGER DEFAULT 0,       -- 1 = the user wrote the bridge line (Claude does not rewrite it)
  final_path    TEXT,
  cost_usd      REAL DEFAULT 0,          -- Studio's Claude cost (the bridge line); Creater keeps its own costs
  created_at    TEXT,
  updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_docext_segment ON docext_jobs(segment_id);
