-- Habla Hermano - Fix Vocabulary Table Columns
-- Run this in Supabase SQL Editor to add any missing columns

-- Base schema column that might be missing
ALTER TABLE vocabulary
ADD COLUMN IF NOT EXISTS times_correct INTEGER NOT NULL DEFAULT 0;

-- Phase 12 SM-2 columns
ALTER TABLE vocabulary
ADD COLUMN IF NOT EXISTS easiness_factor FLOAT DEFAULT 2.5,
ADD COLUMN IF NOT EXISTS interval_days INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS repetition_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_reviewed_at TIMESTAMPTZ;

-- Index for efficient due word queries
CREATE INDEX IF NOT EXISTS idx_vocabulary_next_review
ON vocabulary(user_id, language, next_review_at)
WHERE next_review_at IS NOT NULL;
