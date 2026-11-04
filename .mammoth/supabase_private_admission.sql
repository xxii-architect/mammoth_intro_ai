-- Cross-replica replacement for the private login-wide SQLite completion ledger.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_private_runtime_policy (
    namespace text NOT NULL,
    user_id text NOT NULL,
    daily_tokens bigint CHECK (daily_tokens BETWEEN 0 AND 100000000),
    PRIMARY KEY(namespace,user_id)
);
CREATE TABLE IF NOT EXISTS public.mammoth_private_runtime_attempts (
    namespace text NOT NULL,
    user_id text NOT NULL,
    id text NOT NULL,
    day text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    started_at text NOT NULL,
    finished_at text,
    reserved bigint NOT NULL CHECK (reserved > 0),
    reported bigint CHECK (reported >= 0),
    status text NOT NULL CHECK (status IN ('pending','completed','completed_unknown','failed_unknown')),
    PRIMARY KEY(namespace,user_id,id),
    FOREIGN KEY(namespace,user_id) REFERENCES public.mammoth_private_runtime_policy(namespace,user_id)
);
CREATE INDEX IF NOT EXISTS mammoth_private_attempt_day
    ON public.mammoth_private_runtime_attempts(namespace,user_id,day);
ALTER TABLE public.mammoth_private_runtime_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_private_runtime_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_private_runtime_policy,public.mammoth_private_runtime_attempts
    FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mammoth_private_runtime_policy,public.mammoth_private_runtime_attempts
    TO service_role;
COMMIT;
