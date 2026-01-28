-- Habla Hermano - Database Schema Reference
-- Phase 7: Progress Tracking Tables
-- Apply to Supabase via SQL Editor

-- ============================================
-- VOCABULARY TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS vocabulary (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL, -- No FK: guest session UUIDs are not in auth.users
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('es', 'de', 'fr')),
    part_of_speech TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    times_seen INTEGER NOT NULL DEFAULT 1,
    times_correct INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, word, language)
);

CREATE INDEX idx_vocabulary_user_language ON vocabulary(user_id, language);
CREATE INDEX idx_vocabulary_first_seen ON vocabulary(user_id, first_seen_at DESC);

-- RLS
ALTER TABLE vocabulary ENABLE ROW LEVEL SECURITY;
CREATE POLICY vocabulary_user_policy ON vocabulary
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ============================================
-- LEARNING SESSIONS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS learning_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL, -- No FK: guest session UUIDs are not in auth.users
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    language TEXT NOT NULL CHECK (language IN ('es', 'de', 'fr')),
    level TEXT NOT NULL CHECK (level IN ('A0', 'A1', 'A2', 'B1')),
    messages_count INTEGER NOT NULL DEFAULT 0,
    words_learned INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_sessions_user ON learning_sessions(user_id);
CREATE INDEX idx_sessions_started ON learning_sessions(user_id, started_at DESC);

-- RLS
ALTER TABLE learning_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY sessions_user_policy ON learning_sessions
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ============================================
-- LESSON PROGRESS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS lesson_progress (
    user_id UUID NOT NULL, -- No FK: guest session UUIDs are not in auth.users
    lesson_id TEXT NOT NULL,
    completed_at TIMESTAMPTZ,
    score INTEGER CHECK (score >= 0 AND score <= 100),
    PRIMARY KEY (user_id, lesson_id)
);

CREATE INDEX idx_lesson_progress_user ON lesson_progress(user_id);
CREATE INDEX idx_lesson_progress_completed ON lesson_progress(user_id, completed_at DESC);

-- RLS
ALTER TABLE lesson_progress ENABLE ROW LEVEL SECURITY;
CREATE POLICY lesson_progress_user_policy ON lesson_progress
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ============================================
-- USER PROFILES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    preferred_language TEXT NOT NULL DEFAULT 'es',
    current_level TEXT NOT NULL DEFAULT 'A1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY profiles_user_policy ON user_profiles
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);
