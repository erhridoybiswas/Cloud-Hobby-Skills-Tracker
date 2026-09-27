-- =====================================================================
-- Online Hobby & Skills Tracker — Relational Schema
-- Works unchanged on SQLite (local) and PostgreSQL (Supabase/RDS)
-- with minor type adjustments (TEXT -> VARCHAR, INTEGER -> BOOLEAN).
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------
-- USERS
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    username        TEXT NOT NULL UNIQUE,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    profile_picture TEXT,
    bio             TEXT NOT NULL DEFAULT '',
    interests       TEXT NOT NULL DEFAULT '',
    is_admin        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);

-- ---------------------------------------------------------------
-- SKILLS  (a hobby or a skill the user is learning)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skills (
    skill_id      TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    skill_name    TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'Other',
    current_level TEXT NOT NULL DEFAULT 'BEGINNER',
    target_level  TEXT NOT NULL DEFAULT 'INTERMEDIATE',
    start_date    TEXT,
    target_date   TEXT,
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    CHECK (current_level IN ('BEGINNER','INTERMEDIATE','ADVANCED')),
    CHECK (target_level  IN ('BEGINNER','INTERMEDIATE','ADVANCED')),
    CHECK (status        IN ('ACTIVE','PAUSED','COMPLETED'))
);
CREATE INDEX IF NOT EXISTS idx_skills_user     ON skills(user_id);
CREATE INDEX IF NOT EXISTS idx_skills_name     ON skills(skill_name);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_status   ON skills(status);

-- ---------------------------------------------------------------
-- GOALS  (a measurable target attached to a skill)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goals (
    goal_id       TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    skill_id      TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    target_value  REAL NOT NULL,
    current_value REAL NOT NULL DEFAULT 0,
    unit          TEXT NOT NULL DEFAULT 'hours',   -- hours | minutes | sessions
    deadline      TEXT,
    status        TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | COMPLETED | PAUSED
    created_at    TEXT NOT NULL,
    CHECK (target_value > 0),
    CHECK (unit IN ('hours','minutes','sessions')),
    CHECK (status IN ('ACTIVE','COMPLETED','PAUSED'))
);
CREATE INDEX IF NOT EXISTS idx_goals_user  ON goals(user_id);
CREATE INDEX IF NOT EXISTS idx_goals_skill ON goals(skill_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);

-- ---------------------------------------------------------------
-- MILESTONES  (checkpoints inside a goal)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS milestones (
    milestone_id TEXT PRIMARY KEY,
    goal_id      TEXT NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    target_value REAL NOT NULL,
    achieved     INTEGER NOT NULL DEFAULT 0,
    achieved_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_milestones_goal     ON milestones(goal_id);
CREATE INDEX IF NOT EXISTS idx_milestones_achieved ON milestones(achieved);

-- ---------------------------------------------------------------
-- PRACTICE_SESSIONS
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS practice_sessions (
    session_id       TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    skill_id         TEXT NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    duration_minutes INTEGER NOT NULL,
    activity         TEXT NOT NULL DEFAULT '',
    notes            TEXT NOT NULL DEFAULT '',
    practiced_at     TEXT NOT NULL,   -- ISO date: YYYY-MM-DD
    created_at       TEXT NOT NULL,
    CHECK (duration_minutes > 0 AND duration_minutes <= 1440)
);
CREATE INDEX IF NOT EXISTS idx_practice_user  ON practice_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_practice_skill ON practice_sessions(skill_id);
CREATE INDEX IF NOT EXISTS idx_practice_date  ON practice_sessions(practiced_at);

-- ---------------------------------------------------------------
-- POSTS  (community sharing)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    post_id    TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    skill_id   TEXT REFERENCES skills(skill_id) ON DELETE SET NULL,
    content    TEXT NOT NULL,
    media_url  TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_user    ON posts(user_id);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_skill   ON posts(skill_id);

-- ---------------------------------------------------------------
-- LIKES  (join table — duplicate prevention via UNIQUE)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS likes (
    like_id    TEXT PRIMARY KEY,
    post_id    TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE (post_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_likes_post ON likes(post_id);

-- ---------------------------------------------------------------
-- COMMENTS
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
    comment_id TEXT PRIMARY KEY,
    post_id    TEXT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);

-- ---------------------------------------------------------------
-- FOLLOWS  (optional social graph)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS follows (
    follow_id    TEXT PRIMARY KEY,
    follower_id  TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    following_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    UNIQUE (follower_id, following_id),
    CHECK (follower_id <> following_id)
);
CREATE INDEX IF NOT EXISTS idx_follows_follower  ON follows(follower_id);
CREATE INDEX IF NOT EXISTS idx_follows_following ON follows(following_id);

-- ---------------------------------------------------------------
-- FILES  (metadata for objects stored in cloud object storage)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS files (
    file_id      TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    storage_key  TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    folder       TEXT NOT NULL DEFAULT 'misc',
    is_public    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id);