-- Apply after the tenant baseline. Direct/session-mode PostgreSQL only:
-- transaction-pooling connections cannot hold session advisory run leases.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_agent_runs (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 256),
    id text NOT NULL CHECK (id ~ '^run-[a-f0-9]{16}$'),
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    cancellation_requested boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (namespace, user_id, id),
    CHECK (payload ?& ARRAY['id','user_id','storage_revision']),
    CHECK (payload->>'id' = id AND payload->>'user_id' = user_id),
    CHECK ((payload->>'storage_revision')::bigint = revision)
);
CREATE INDEX IF NOT EXISTS mammoth_agent_runs_recent
    ON public.mammoth_agent_runs(namespace,user_id,updated_at DESC,id);
ALTER TABLE public.mammoth_agent_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_agent_runs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.mammoth_agent_runs TO service_role;
COMMIT;
