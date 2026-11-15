-- Creater Vid: video projects of two kinds (documentary, news) and their steps, the chat with Claude, the two rulebooks.
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS projects (
  id               INTEGER PRIMARY KEY,
  kind             TEXT DEFAULT 'doc',     -- doc (documentary) | news (Tin tức desk): own workflow and rulebook
  slug             TEXT NOT NULL UNIQUE,
  title            TEXT NOT NULL,
  topic            TEXT NOT NULL,          -- what the film is about
  brief            TEXT,                   -- the user's notes: angle, must-haves, things to avoid
  language         TEXT DEFAULT 'en',      -- on-screen text and narration
  audience         TEXT,
  style            TEXT,                   -- visual style string (empty = Claude proposes one in step 1)
  format           TEXT DEFAULT '16:9',    -- 16:9 | 9:16
  target_sec       INTEGER,
  budget_usd       REAL,                   -- USD of generated assets (voice, images, video) the project may spend without asking
  use_jre          INTEGER DEFAULT 0,      -- 1 = the JRE highlight database is a source
  auto_advance     INTEGER DEFAULT 0,      -- 1 = run every step without waiting for approval
  pipeline         TEXT DEFAULT 'layered', -- layered (cut-outs on plates) | fullframe (one image per scene -> 3D camera)
  yt_profile       TEXT,                   -- GPM Login profile that uploads the video
  yt_channel       TEXT,                   -- YouTube channel id (UC…) inside that profile
  yt_auto          INTEGER DEFAULT 0,
  claude_model     TEXT,                   -- this project's Claude model (empty = the desk default, then settings)
  claude_effort    TEXT,                   -- this project's effort: low | medium | high | xhigh | max (empty = desk default)      -- 1 = upload by itself when the metadata step is approved; 0 = the user clicks Đăng
  dir              TEXT NOT NULL,          -- project folder
  session_id       TEXT,                   -- Claude Code session shared by every turn of the project
  session_cost_usd REAL,                   -- total_cost_usd of that session (cumulative, as the CLI reports it)
  rules_version    INTEGER,                -- rulebook version the session was last told about
  cost_usd         REAL DEFAULT 0,         -- Claude cost of the project so far
  archived         INTEGER DEFAULT 0,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);

-- One row per project and step of its kind's workflow (doc: script, cast, scenes, images, footage, render, metadata)
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
  version     INTEGER PRIMARY KEY,         -- row id: what projects.rules_version and the API refer to
  book        TEXT DEFAULT 'doc',          -- doc | news: each kind of video has its own rulebook
  num         INTEGER,                     -- version number within the book (what the pages show)
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

-- News desk: topics the app watches in real time, their sources, and every item fetched from them.
CREATE TABLE IF NOT EXISTS news_topics (
  id             INTEGER PRIMARY KEY,
  name           TEXT NOT NULL,
  language       TEXT DEFAULT 'ru',      -- language of the videos made from this topic (and of news searches)
  keywords       TEXT,                   -- one term per line, matched at the start of a word: filtered sources keep matches only
  exclude        TEXT,                   -- one term per line: an item containing one is dropped
  interval_min   INTEGER DEFAULT 10,     -- minutes between two polls
  enabled        INTEGER DEFAULT 1,
  brief          TEXT,                   -- default brief of a video made from this topic
  format         TEXT DEFAULT '9:16',
  target_sec     INTEGER DEFAULT 60,
  video_kind     TEXT DEFAULT 'single',  -- single (one story) | digest ("Điểm tin 24h", RULEBOOK 2.9)
  last_polled_at TEXT,
  last_new       INTEGER,                -- items added by the last poll
  created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_sources (
  id           INTEGER PRIMARY KEY,
  topic_id     INTEGER NOT NULL REFERENCES news_topics(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL,            -- rss | telegram | bing | gnews
  url          TEXT NOT NULL,            -- feed URL, Telegram channel, or search query
  name         TEXT,
  side         TEXT DEFAULT '',          -- who is speaking: ru | ua | intl | indep | '' (unknown)
  filter       INTEGER DEFAULT 1,        -- 1 = keep only items matching the topic keywords
  enabled      INTEGER DEFAULT 1,
  last_ok_at   TEXT,
  last_try_at  TEXT,
  last_error   TEXT,
  last_count   INTEGER,                  -- items kept by the last fetch (after the keyword filter)
  last_new     INTEGER,                  -- of which new
  fail_count   INTEGER DEFAULT 0,
  etag         TEXT,
  modified     TEXT,
  created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_sources_topic ON news_sources(topic_id);

CREATE TABLE IF NOT EXISTS news_items (
  id           INTEGER PRIMARY KEY,
  topic_id     INTEGER NOT NULL REFERENCES news_topics(id) ON DELETE CASCADE,
  source_id    INTEGER REFERENCES news_sources(id) ON DELETE SET NULL,
  uid          TEXT NOT NULL,            -- canonical link (or guid): one item per topic
  url          TEXT,
  title        TEXT NOT NULL,
  summary      TEXT,
  body         TEXT,                     -- full text: from the feed, or read from the page on demand
  fetch_error  TEXT,                     -- why the full text could not be read
  image        TEXT,
  source_name  TEXT,                     -- outlet named by a search result (Bing/Google News)
  extra        TEXT,                     -- JSON: Telegram views, has video
  published_at TEXT,
  fetched_at   TEXT NOT NULL,
  matched      TEXT,                     -- topic keywords found in the item, comma separated
  score        INTEGER DEFAULT 0,        -- how many of them
  story_id     INTEGER,                  -- first item of the same event told by several sources
  state        TEXT DEFAULT 'new',       -- new | seen | starred | hidden | used
  project_id   INTEGER,                  -- video project made from it
  UNIQUE(topic_id, uid)
);
CREATE INDEX IF NOT EXISTS idx_news_items_time ON news_items(topic_id, published_at);
CREATE INDEX IF NOT EXISTS idx_news_items_story ON news_items(story_id);

-- YouTube channels found inside each GPM Login profile (creater/publish.py scans them) and the last scan of a profile.
CREATE TABLE IF NOT EXISTS yt_channels (
  profile_id    TEXT NOT NULL,
  channel_id    TEXT NOT NULL,
  profile_name  TEXT,
  name          TEXT,
  handle        TEXT,
  subs          TEXT,
  photo         TEXT,
  scanned_at    TEXT,
  PRIMARY KEY (profile_id, channel_id)
);
CREATE TABLE IF NOT EXISTS yt_scans (
  profile_id    TEXT PRIMARY KEY,
  profile_name  TEXT,
  ok            INTEGER,
  error         TEXT,
  count         INTEGER,
  scanned_at    TEXT
);
