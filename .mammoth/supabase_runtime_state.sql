-- Apply after supabase_tenant_auth.sql. Service-only operational records.
-- No product tables, public content or client RLS grants are changed.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_runtime_state (
    key text PRIMARY KEY CHECK (length(key) BETWEEN 1 AND 512),
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.mammoth_runtime_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_runtime_state FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.mammoth_runtime_state TO service_role;

CREATE OR REPLACE FUNCTION public.mammoth_state_read(p_key text)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT coalesce(
        (SELECT jsonb_build_object('revision', revision, 'payload', payload)
         FROM public.mammoth_runtime_state WHERE key = p_key),
        jsonb_build_object('revision', 0, 'payload', NULL))
$$;

CREATE OR REPLACE FUNCTION public.mammoth_state_cas(p_key text, p_revision bigint, p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE next_revision bigint;
BEGIN
    IF p_revision IS NULL OR p_revision < 0 OR p_payload IS NULL THEN
        RAISE EXCEPTION 'Invalid state update';
    END IF;
    IF p_revision = 0 THEN
        INSERT INTO public.mammoth_runtime_state(key, revision, payload)
        VALUES(p_key, 1, p_payload) ON CONFLICT DO NOTHING
        RETURNING revision INTO next_revision;
    ELSE
        UPDATE public.mammoth_runtime_state SET payload=p_payload,
            revision=revision+1, updated_at=clock_timestamp()
        WHERE key=p_key AND revision=p_revision RETURNING revision INTO next_revision;
    END IF;
    RETURN jsonb_build_object('saved', next_revision IS NOT NULL, 'revision', next_revision);
END $$;

REVOKE ALL ON FUNCTION public.mammoth_state_read(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.mammoth_state_cas(text,bigint,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.mammoth_state_read(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.mammoth_state_cas(text,bigint,jsonb) TO service_role;
COMMIT;
