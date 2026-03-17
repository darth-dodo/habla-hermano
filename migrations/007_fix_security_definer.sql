-- Habla Hermano - Schema Migration: Fix SECURITY DEFINER → SECURITY INVOKER
--
-- The original migration (003) created vocabulary RPC functions as SECURITY DEFINER,
-- which means they execute with the function owner's (superuser) privileges and bypass
-- all RLS policies. This allowed any authenticated user to pass another user's UUID
-- and modify their vocabulary records.
--
-- This migration redefines all 4 functions as SECURITY INVOKER so they respect RLS
-- and execute with the calling user's privileges.
--
-- Apply to Supabase via SQL Editor.

-- ============================================
-- 1. ATOMIC INCREMENT: times_correct (SECURITY INVOKER)
-- ============================================
CREATE OR REPLACE FUNCTION vocabulary_increment_correct(
    p_vocab_id BIGINT,
    p_user_id UUID
)
RETURNS INTEGER
LANGUAGE sql
SECURITY INVOKER
AS $$
    UPDATE vocabulary
    SET times_correct = times_correct + 1
    WHERE id = p_vocab_id
      AND user_id = p_user_id
    RETURNING times_correct;
$$;

-- ============================================
-- 2. ATOMIC INCREMENT: times_seen (SECURITY INVOKER)
-- ============================================
CREATE OR REPLACE FUNCTION vocabulary_increment_seen(
    p_vocab_id BIGINT,
    p_user_id UUID
)
RETURNS INTEGER
LANGUAGE sql
SECURITY INVOKER
AS $$
    UPDATE vocabulary
    SET times_seen = times_seen + 1
    WHERE id = p_vocab_id
      AND user_id = p_user_id
    RETURNING times_seen;
$$;

-- ============================================
-- 3. ATOMIC INCREMENT: times_seen on upsert fallback (SECURITY INVOKER)
-- ============================================
CREATE OR REPLACE FUNCTION vocabulary_upsert_increment(
    p_user_id UUID,
    p_word TEXT,
    p_language TEXT,
    p_translation TEXT,
    p_part_of_speech TEXT DEFAULT NULL
)
RETURNS SETOF vocabulary
LANGUAGE sql
SECURITY INVOKER
AS $$
    UPDATE vocabulary
    SET times_seen = times_seen + 1,
        translation = p_translation,
        part_of_speech = COALESCE(p_part_of_speech, part_of_speech)
    WHERE user_id = p_user_id
      AND word = p_word
      AND language = p_language
    RETURNING *;
$$;

-- ============================================
-- 4. OPTIMISTIC SM-2 UPDATE (SECURITY INVOKER)
-- ============================================
CREATE OR REPLACE FUNCTION vocabulary_update_sm2(
    p_vocab_id BIGINT,
    p_user_id UUID,
    p_easiness_factor DOUBLE PRECISION,
    p_interval_days INTEGER,
    p_repetition_count INTEGER,
    p_next_review_at TIMESTAMPTZ,
    p_last_reviewed_at TIMESTAMPTZ,
    p_expected_repetition_count INTEGER,
    p_quality INTEGER
)
RETURNS SETOF vocabulary
LANGUAGE sql
SECURITY INVOKER
AS $$
    UPDATE vocabulary
    SET easiness_factor = p_easiness_factor,
        interval_days = p_interval_days,
        repetition_count = p_repetition_count,
        next_review_at = p_next_review_at,
        last_reviewed_at = p_last_reviewed_at,
        times_seen = times_seen + 1,
        times_correct = CASE
            WHEN p_quality >= 3 THEN times_correct + 1
            ELSE times_correct
        END
    WHERE id = p_vocab_id
      AND user_id = p_user_id
      AND repetition_count = p_expected_repetition_count
    RETURNING *;
$$;
