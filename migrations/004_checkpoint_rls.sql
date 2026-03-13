-- Migration 004: Enable RLS on LangGraph checkpoint tables
--
-- LangGraph creates 4 tables with no RLS:
--   checkpoint_migrations  — schema versioning (no user data)
--   checkpoints            — conversation state snapshots
--   checkpoint_blobs       — serialized channel data (messages, etc.)
--   checkpoint_writes      — pending writes buffer
--
-- Thread IDs follow these formats:
--   Auth chat:    "user:{auth_uuid}" or "user:{auth_uuid}:{version}"
--   Auth lesson:  "lesson:{auth_uuid}:{lesson_id}:{session}"
--   Guest:        "{session_uuid}" or "lesson:{session_uuid}:..."
--
-- Policy logic:
--   Extract the user UUID from thread_id (2nd segment after splitting on ':')
--   and compare against auth.uid(). This covers both "user:" and "lesson:" prefixed
--   thread IDs for authenticated users.
--
--   Guest sessions use the service-role client which bypasses RLS entirely,
--   so no guest-specific policy is needed.
--
-- NOTE: Run this in the Supabase SQL Editor after deploying the application
--       (LangGraph must have created the tables via setup() first).

-- =============================================================================
-- Helper: extract user UUID from thread_id
-- =============================================================================

CREATE OR REPLACE FUNCTION checkpoint_owner(thread_id TEXT)
RETURNS UUID
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
  -- Split on ':' and take the 2nd element (index 2 in split_part, 1-based).
  -- "user:abc-123" → "abc-123"
  -- "user:abc-123:v2" → "abc-123"
  -- "lesson:abc-123:es-A0-greetings:sess" → "abc-123"
  -- "bare-session-uuid" → "bare-session-uuid" (will fail UUID cast → NULL)
  SELECT split_part(thread_id, ':', 2)::UUID
$$;

-- =============================================================================
-- checkpoints
-- =============================================================================

ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;

-- Authenticated users can only access their own checkpoints
CREATE POLICY checkpoints_user_policy ON checkpoints
  FOR ALL
  USING (checkpoint_owner(thread_id) = auth.uid())
  WITH CHECK (checkpoint_owner(thread_id) = auth.uid());

-- Service role bypasses RLS (used by server for guests and admin)
CREATE POLICY checkpoints_service_policy ON checkpoints
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- checkpoint_blobs
-- =============================================================================

ALTER TABLE checkpoint_blobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY checkpoint_blobs_user_policy ON checkpoint_blobs
  FOR ALL
  USING (checkpoint_owner(thread_id) = auth.uid())
  WITH CHECK (checkpoint_owner(thread_id) = auth.uid());

CREATE POLICY checkpoint_blobs_service_policy ON checkpoint_blobs
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- checkpoint_writes
-- =============================================================================

ALTER TABLE checkpoint_writes ENABLE ROW LEVEL SECURITY;

CREATE POLICY checkpoint_writes_user_policy ON checkpoint_writes
  FOR ALL
  USING (checkpoint_owner(thread_id) = auth.uid())
  WITH CHECK (checkpoint_owner(thread_id) = auth.uid());

CREATE POLICY checkpoint_writes_service_policy ON checkpoint_writes
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- checkpoint_migrations (no user data, admin-only)
-- =============================================================================

ALTER TABLE checkpoint_migrations ENABLE ROW LEVEL SECURITY;

-- Only service role can read/write migration tracking
CREATE POLICY checkpoint_migrations_service_policy ON checkpoint_migrations
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- Grant execute on helper function
-- =============================================================================

GRANT EXECUTE ON FUNCTION checkpoint_owner(TEXT) TO authenticated, anon, service_role;
