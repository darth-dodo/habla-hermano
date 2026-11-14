-- Habla Hermano - Schema Migration: Phase 12 Spaced Repetition
-- Adds SM-2 algorithm fields to vocabulary table for spaced repetition scheduling.
-- Apply to Supabase via SQL Editor

-- ============================================
-- ADD SM-2 FIELDS TO VOCABULARY TABLE
-- ============================================
ALTER TABLE vocabulary
ADD COLUMN IF NOT EXISTS easiness_factor FLOAT DEFAULT 2.5,
ADD COLUMN IF NOT EXISTS interval_days INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS repetition_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_reviewed_at TIMESTAMPTZ;

-- ============================================
-- INDEX FOR EFFICIENT DUE WORD QUERIES
-- ============================================
-- Partial index for words that are scheduled for review
-- Query pattern: WHERE user_id = :user_id AND language = :lang AND next_review_at <= NOW()
CREATE INDEX IF NOT EXISTS idx_vocabulary_next_review
ON vocabulary(user_id, language, next_review_at)
WHERE next_review_at IS NOT NULL;
