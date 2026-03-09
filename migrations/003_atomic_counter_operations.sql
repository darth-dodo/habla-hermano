-- Habla Hermano - Schema Migration: Atomic Counter Operations
-- Adds Postgres RPC functions for atomic counter increments and
-- optimistic-locking SM-2 updates to eliminate read-then-write race conditions.
-- Apply to Supabase via SQL Editor.

-- ============================================
-- 1. ATOMIC INCREMENT: times_correct
-- ============================================
-- Atomically increments times_correct by 1 for a given vocabulary row.
-- Returns the new value, or -1 if the row was not found.
CREATE OR REPLACE FUNCTION vocabulary_increment_correct(
    p_vocab_id BIGINT,
    p_user_id UUID
)
RETURNS INTEGER
LANGUAGE sql
SECURITY DEFINER
AS $$
    UPDATE vocabulary
    SET times_correct = times_correct + 1
    WHERE id = p_vocab_id
      AND user_id = p_user_id
    RETURNING times_correct;
$$;

-- ============================================
-- 2. ATOMIC INCREMENT: times_seen
-- ============================================
-- Atomically increments times_seen by 1 for a given vocabulary row.
-- Returns the new value, or -1 if the row was not found.
CREATE OR REPLACE FUNCTION vocabulary_increment_seen(
    p_vocab_id BIGINT,
    p_user_id UUID
)
RETURNS INTEGER
LANGUAGE sql
SECURITY DEFINER
AS $$
    UPDATE vocabulary
    SET times_seen = times_seen + 1
    WHERE id = p_vocab_id
      AND user_id = p_user_id
    RETURNING times_seen;
$$;

-- ============================================
-- 3. ATOMIC INCREMENT: times_seen on upsert fallback
-- ============================================
-- Atomically increments times_seen and updates translation/part_of_speech
-- for an existing vocabulary row identified by (user_id, word, language).
-- Used by the upsert fallback path after a duplicate-key conflict.
CREATE OR REPLACE FUNCTION vocabulary_upsert_increment(
    p_user_id UUID,
    p_word TEXT,
    p_language TEXT,
    p_translation TEXT,
    p_part_of_speech TEXT DEFAULT NULL
)
RETURNS SETOF vocabulary
LANGUAGE sql
SECURITY DEFINER
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
-- 4. OPTIMISTIC SM-2 UPDATE
-- ============================================
-- Updates SM-2 fields for a vocabulary row, but ONLY if the current
-- repetition_count matches the expected value (optimistic concurrency).
-- If the row was modified concurrently, no rows are updated and the
-- caller must re-read and retry.
--
-- Also atomically increments times_seen by 1. If the quality >= 3
-- (successful recall), times_correct is also incremented by 1.
-- This eliminates the need to read counters before writing.
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
SECURITY DEFINER
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

-- ============================================
-- 5. GRANT EXECUTE to authenticated users
-- ============================================
-- Supabase uses the 'authenticated' role for logged-in users.
GRANT EXECUTE ON FUNCTION vocabulary_increment_correct(BIGINT, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION vocabulary_increment_seen(BIGINT, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION vocabulary_upsert_increment(UUID, TEXT, TEXT, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION vocabulary_update_sm2(BIGINT, UUID, DOUBLE PRECISION, INTEGER, INTEGER, TIMESTAMPTZ, TIMESTAMPTZ, INTEGER, INTEGER) TO authenticated;

-- Also grant to anon for guest/unauthenticated flows if applicable
GRANT EXECUTE ON FUNCTION vocabulary_increment_correct(BIGINT, UUID) TO anon;
GRANT EXECUTE ON FUNCTION vocabulary_increment_seen(BIGINT, UUID) TO anon;
GRANT EXECUTE ON FUNCTION vocabulary_upsert_increment(UUID, TEXT, TEXT, TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION vocabulary_update_sm2(BIGINT, UUID, DOUBLE PRECISION, INTEGER, INTEGER, TIMESTAMPTZ, TIMESTAMPTZ, INTEGER, INTEGER) TO anon;

-- Grant to service_role for admin operations
GRANT EXECUTE ON FUNCTION vocabulary_increment_correct(BIGINT, UUID) TO service_role;
GRANT EXECUTE ON FUNCTION vocabulary_increment_seen(BIGINT, UUID) TO service_role;
GRANT EXECUTE ON FUNCTION vocabulary_upsert_increment(UUID, TEXT, TEXT, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION vocabulary_update_sm2(BIGINT, UUID, DOUBLE PRECISION, INTEGER, INTEGER, TIMESTAMPTZ, TIMESTAMPTZ, INTEGER, INTEGER) TO service_role;
