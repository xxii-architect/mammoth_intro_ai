-- MammothOS ATLAS — Supabase Schema Supplement
-- Safe to re-run: uses IF NOT EXISTS for tables/indexes and
-- DROP POLICY IF EXISTS before each CREATE POLICY (Postgres has no
-- "CREATE POLICY IF NOT EXISTS" syntax).
--
-- Tables managed here:
--   mammoth.ai_sessions — log every CodingAgent LLM call
--   atlas.sessions      — one row per ATLAS CLI/API learning session
--   atlas.exercises     — generated exercises per session/lesson
--
-- Run this in Supabase SQL Editor: project > SQL Editor > New Query
-- ─────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────
-- mammoth.ai_sessions — log CodingAgent LLM calls (from atlas code generate)
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mammoth.ai_sessions (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    prompt       TEXT        NOT NULL,
    response     TEXT,
    tokens_used  INTEGER,
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE mammoth.ai_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access to ai_sessions" ON mammoth.ai_sessions;
CREATE POLICY "Service role full access to ai_sessions"
    ON mammoth.ai_sessions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT SELECT, INSERT ON mammoth.ai_sessions TO service_role;

-- ─────────────────────────────────────────────────────────────────────────
-- atlas.sessions — track individual ATLAS learning sessions
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlas.sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic       TEXT        NOT NULL,
    difficulty  TEXT        NOT NULL DEFAULT 'beginner',
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    status      TEXT        NOT NULL DEFAULT 'active'  -- active | completed | abandoned
);

ALTER TABLE atlas.sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users access own sessions" ON atlas.sessions;
CREATE POLICY "Users access own sessions"
    ON atlas.sessions
    FOR ALL
    USING (user_id = auth.uid());

GRANT SELECT, INSERT, UPDATE ON atlas.sessions TO service_role;


-- ─────────────────────────────────────────────────────────────────────────
-- atlas.exercises — generated exercises per session/lesson
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlas.exercises (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES atlas.sessions(id) ON DELETE CASCADE,
    curriculum_id       TEXT        NOT NULL,
    lesson_id           UUID REFERENCES atlas.atlas_lessons(id) ON DELETE SET NULL,
    title               TEXT        NOT NULL,
    prompt              TEXT        NOT NULL,
    difficulty          TEXT        NOT NULL DEFAULT 'beginner',
    generation_method   TEXT        NOT NULL DEFAULT 'template',  -- template | llm
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE atlas.exercises ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users access exercises via session" ON atlas.exercises;
CREATE POLICY "Users access exercises via session"
    ON atlas.exercises
    FOR ALL
    USING (
        session_id IN (
            SELECT id FROM atlas.sessions WHERE user_id = auth.uid()
        )
    );

GRANT SELECT, INSERT ON atlas.exercises TO service_role;


-- ─────────────────────────────────────────────────────────────────────────
-- atlas.lesson_chunks — persistent RAG chunks for lesson content
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS atlas.lesson_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id     UUID NOT NULL REFERENCES atlas.atlas_lessons(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    chunk_text    TEXT NOT NULL,
    chunk_length  INTEGER NOT NULL DEFAULT 0,
    embedding     vector(1536),
    metadata      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE atlas.lesson_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access to lesson_chunks" ON atlas.lesson_chunks;
CREATE POLICY "Service role full access to lesson_chunks"
    ON atlas.lesson_chunks
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON atlas.lesson_chunks TO service_role;

CREATE INDEX IF NOT EXISTS idx_lesson_chunks_lesson_order
    ON atlas.lesson_chunks (lesson_id, chunk_index);


-- ─────────────────────────────────────────────────────────────────────────
-- Useful indexes
-- ─────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_exercises_curriculum_lesson
    ON atlas.exercises (curriculum_id, lesson_id);

CREATE INDEX IF NOT EXISTS idx_adaptive_metrics_user_lesson
    ON atlas.adaptive_metrics (user_id, lesson_id);


-- ─────────────────────────────────────────────────────────────────────────
-- XP increment function — called by TutorAgent on each pass
-- Safely increments xp + lessons_completed without a read-modify-write race.
-- ─────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION atlas.award_xp(
    p_user_id UUID,
    p_xp      INTEGER DEFAULT 10
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    INSERT INTO atlas.community_stats (user_id, xp, lessons_completed, last_active)
    VALUES (p_user_id, p_xp, 1, now())
    ON CONFLICT (user_id) DO UPDATE
        SET xp                = atlas.community_stats.xp + p_xp,
            lessons_completed = atlas.community_stats.lessons_completed + 1,
            last_active       = now();
END;
$$;
