-- JRE Studio database schema (SQLite + FTS5)
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
  session_cost_usd  REAL                  -- total_cost_usd reported by the CLI (cumulative over a resumed session)
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

-- Make Documentary Film tab (studio/docfilm): projects, their chat with Claude, rulebook history
CREATE TABLE IF NOT EXISTS docfilm_projects (
  id               INTEGER PRIMARY KEY,
  slug             TEXT NOT NULL UNIQUE,
  title            TEXT NOT NULL,
  topic            TEXT NOT NULL,          -- what the film is about (seed of the database search)
  brief            TEXT,                   -- the user's notes: angle, audience, must-have segments, ...
  format           TEXT DEFAULT '16:9',    -- 16:9 | 9:16
  target_sec       INTEGER,
  credit_budget    REAL,                   -- Higgsfield credits the project may spend without asking
  stage            TEXT NOT NULL DEFAULT 'new',   -- new | research | script | film (computed from its files)
  dir              TEXT NOT NULL,          -- project folder
  session_id       TEXT,                   -- Claude Code session shared by every turn of the project
  session_cost_usd REAL,                   -- total_cost_usd of that session (cumulative, as the CLI reports it)
  rules_version    INTEGER,                -- rulebook version the session was last told about
  cost_usd         REAL DEFAULT 0,         -- Claude cost of the project so far
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS docfilm_messages (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL REFERENCES docfilm_projects(id) ON DELETE CASCADE,
  role          TEXT NOT NULL,             -- user | assistant
  kind          TEXT NOT NULL DEFAULT 'chat',   -- chat | research | script | build
  content       TEXT,                      -- user text, or Claude's final answer (markdown)
  log_md        TEXT,                      -- assistant: every text block of the run (progress notes included)
  status        TEXT NOT NULL DEFAULT 'done',   -- assistant: queued | running | done | failed
  progress_msg  TEXT,
  reply_to      INTEGER,                   -- assistant: the user message it answers
  model         TEXT,
  effort        TEXT,
  models_used   TEXT,
  usage_json    TEXT,
  cost_usd      REAL,                      -- this turn only
  duration_sec  REAL,
  session_id    TEXT,
  rules_version INTEGER,                   -- set when the turn changed the rulebook
  error         TEXT,
  created_at    TEXT NOT NULL,
  started_at    TEXT,
  finished_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_docfilm_messages_project ON docfilm_messages(project_id);
CREATE TABLE IF NOT EXISTS docfilm_rules (
  version     INTEGER PRIMARY KEY,
  body        TEXT NOT NULL,
  source      TEXT,                        -- seed | claude | manual | file | restore
  project_id  INTEGER,
  message_id  INTEGER,
  note        TEXT,
  created_at  TEXT NOT NULL
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
