-- MammothOS ATLAS — Supabase Schema Supplement
-- The primary atlas schema tables (atlas_lessons, atlas_progress,
-- adaptive_metrics, community_stats, atlas_sel_checkins, insight_reports,
-- leaderboard) already exist in the `atlas` schema.
--
-- This file adds only the tables that are NOT yet in the atlas schema:
--   atlas.sessions   — one row per ATLAS CLI/API learning session
--   atlas.exercises  — generated exercises per session/lesson
--
-- Run this in Supabase SQL Editor: project > SQL Editor > New Query
-- ─────────────────────────────────────────────────────────────────────────

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

CREATE POLICY "Users access own sessions"
    ON atlas.sessions
    FOR ALL
    USING (user_id = auth.uid());


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

CREATE POLICY "Users access exercises via session"
    ON atlas.exercises
    FOR ALL
    USING (
        session_id IN (
            SELECT id FROM atlas.sessions WHERE user_id = auth.uid()
        )
    );


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
