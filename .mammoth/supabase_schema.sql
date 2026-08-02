-- MammothOS ATLAS Supabase Schema
-- Run this in your Supabase SQL editor (project > SQL Editor > New Query)
-- All tables live in the public schema and use RLS (Row Level Security)

-- ─────────────────────────────────────────────────────────────
-- sessions: one row per ATLAS learning session
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT        NOT NULL,
    topic       TEXT        NOT NULL,
    difficulty  TEXT        NOT NULL DEFAULT 'beginner',
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    status      TEXT        NOT NULL DEFAULT 'active'  -- active | completed | abandoned
);

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own sessions"
    ON public.sessions
    FOR ALL
    USING (user_id = auth.uid()::text);


-- ─────────────────────────────────────────────────────────────
-- exercises: generated exercises per session / lesson
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.exercises (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    curriculum_id       TEXT        NOT NULL,
    lesson_id           TEXT        NOT NULL,
    title               TEXT        NOT NULL,
    prompt              TEXT        NOT NULL,
    difficulty          TEXT        NOT NULL DEFAULT 'beginner',
    generation_method   TEXT        NOT NULL DEFAULT 'template',  -- template | llm
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.exercises ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access exercises via session"
    ON public.exercises
    FOR ALL
    USING (
        session_id IN (
            SELECT id FROM public.sessions WHERE user_id = auth.uid()::text
        )
    );


-- ─────────────────────────────────────────────────────────────
-- progress: one row per submission attempt
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.progress (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT        NOT NULL,
    curriculum_id       TEXT        NOT NULL,
    lesson_id           TEXT        NOT NULL,
    exercise_id         UUID REFERENCES public.exercises(id) ON DELETE SET NULL,
    passed              BOOLEAN     NOT NULL,
    attempt_index       INTEGER     NOT NULL DEFAULT 0,
    duration_ms         INTEGER,
    error_fingerprint   TEXT,       -- passed | syntax_error | assertion_error | …
    stdout              TEXT,
    stderr              TEXT,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.progress ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own progress"
    ON public.progress
    FOR ALL
    USING (user_id = auth.uid()::text);


-- ─────────────────────────────────────────────────────────────
-- Useful indexes
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_progress_user_lesson
    ON public.progress (user_id, curriculum_id, lesson_id);

CREATE INDEX IF NOT EXISTS idx_exercises_curriculum_lesson
    ON public.exercises (curriculum_id, lesson_id);
