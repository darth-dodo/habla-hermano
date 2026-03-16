-- Migration 005: Conversation threads metadata table
-- Phase 26: Add sidebar thread list for authenticated users.
--
-- Stores thread metadata (title, language, timestamps) separately from
-- LangGraph checkpoint data. The thread_id column bridges this table
-- to the checkpoint tables.
--
-- Thread ID format: "user:{auth_uuid}:{thread_uuid}"
-- RLS: users see only their own threads via auth.uid().
--
-- NOTE: Run this in the Supabase SQL Editor.

CREATE TABLE conversation_threads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    thread_id   TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL DEFAULT 'New conversation',
    language    TEXT NOT NULL DEFAULT 'es',
    level       TEXT NOT NULL DEFAULT 'A1',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE conversation_threads ENABLE ROW LEVEL SECURITY;

CREATE POLICY threads_user_policy ON conversation_threads
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY threads_service_policy ON conversation_threads
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX idx_threads_user_updated ON conversation_threads(user_id, updated_at DESC);
