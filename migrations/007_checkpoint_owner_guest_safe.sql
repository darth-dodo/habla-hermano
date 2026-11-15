-- 007: checkpoint_owner() returns NULL for guest thread IDs instead of raising.
--
-- Guest chats use a bare session UUID as thread_id (no "user:" prefix), so
-- split_part(thread_id, ':', 2) is '' and ''::UUID raises "invalid input
-- syntax for type uuid". RLS evaluates the policy on every row a user's
-- query scans, so once any guest had chatted, a signed-in user's
-- "Delete all conversations" (a LIKE filter) failed and deleted nothing.
--
-- Now only a well-formed UUID is cast; anything else gives NULL, which never
-- equals auth.uid(), so guest rows stay invisible to signed-in users.
-- Apply in the Supabase SQL editor. Safe to re-run.

CREATE OR REPLACE FUNCTION checkpoint_owner(thread_id TEXT)
RETURNS UUID
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = ''
AS $$
  SELECT CASE
    WHEN split_part(thread_id, ':', 2)
         ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    THEN split_part(thread_id, ':', 2)::UUID
  END
$$;
