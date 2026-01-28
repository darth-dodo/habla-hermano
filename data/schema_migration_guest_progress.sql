-- Habla Hermano - Schema Migration: Guest Progress Tracking
-- Drops FK constraints on progress tables so guest session UUIDs
-- (not in auth.users) can be stored in the user_id column.
-- The service-role client bypasses RLS for guest operations.

-- Drop FK constraints (vocabulary, learning_sessions, lesson_progress)
ALTER TABLE vocabulary DROP CONSTRAINT IF EXISTS vocabulary_user_id_fkey;
ALTER TABLE learning_sessions DROP CONSTRAINT IF EXISTS learning_sessions_user_id_fkey;
ALTER TABLE lesson_progress DROP CONSTRAINT IF EXISTS lesson_progress_user_id_fkey;

-- user_profiles FK stays intact (guests don't need profiles)
