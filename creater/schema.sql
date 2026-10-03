-- Creater Vid: documentary projects, their six steps, the chat with Claude, the rulebook history.
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS projects (
  id               INTEGER PRIMARY KEY,
  slug             TEXT NOT NULL UNIQUE,
  title            TEXT NOT NULL,
  topic            TEXT NOT NULL,          -- what the film is about
  brief            TEXT,                   -- the user's notes: angle, must-haves, things to avoid
  language         TEXT DEFAULT 'en',      -- on-screen text and narration
  audience         TEXT,
  style            TEXT,                   -- visual style string (empty = Claude proposes one in step 1)
  format           TEXT DEFAULT '16:9',    -- 16:9 | 9:16
  target_sec       INTEGER,
  credit_budget    REAL,                   -- Higgsfield credits the project may spend without asking
  use_jre          INTEGER DEFAULT 0,      -- 1 = the JRE highlight database is a source
  auto_advance     INTEGER DEFAULT 0,      -- 1 = run every step without waiting for approval
  dir              TEXT NOT NULL,          -- project folder
  session_id       TEXT,                   -- Claude Code session shared by every turn of the project
  session_cost_usd REAL,                   -- total_cost_usd of that session (cumulative, as the CLI reports it)
  rules_version    INTEGER,                -- rulebook version the session was last told about
  cost_usd         REAL DEFAULT 0,         -- Claude cost of the project so far
  archived         INTEGER DEFAULT 0,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);

-- One row per project and step (script, cast, scenes, images, footage, render)
CREATE TABLE IF NOT EXISTS project_steps (
  project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  step         TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'locked',  -- locked | ready | queued | running | review | approved | failed
  runs         INTEGER DEFAULT 0,
  message_id   INTEGER,                   -- last assistant turn that ran the step
  started_at   TEXT,
  finished_at  TEXT,
  approved_at  TEXT,
  problems     TEXT,                      -- JSON list: what the output check found after the last run
  error        TEXT,
  PRIMARY KEY (project_id, step)
);

CREATE TABLE IF NOT EXISTS messages (
  id            INTEGER PRIMARY KEY,
  project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role          TEXT NOT NULL,             -- user | assistant
  kind          TEXT NOT NULL DEFAULT 'chat',   -- chat | step
  step          TEXT,                      -- step it runs (kind=step) or the step the user was looking at (chat)
  content       TEXT,                      -- user text, or Claude's final answer (markdown)
  log_md        TEXT,                      -- assistant: every text block of the run
  status        TEXT NOT NULL DEFAULT 'done',   -- assistant: queued | running | done | failed
  progress_msg  TEXT,
  reply_to      INTEGER,
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
CREATE INDEX IF NOT EXISTS idx_messages_project ON messages(project_id);

CREATE TABLE IF NOT EXISTS rules (
  version     INTEGER PRIMARY KEY,
  body        TEXT NOT NULL,
  source      TEXT,                        -- seed | claude | manual | file | restore
  project_id  INTEGER,
  message_id  INTEGER,
  note        TEXT,
  created_at  TEXT NOT NULL
);

-- Activity log shown on the project page and on the Activity page
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER,
  step        TEXT,
  kind        TEXT NOT NULL,               -- created | run | done | failed | approved | reopened | sources | cast | footage | redo | edit
  text        TEXT,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id);
