-- Private per-login learning admission and cancellation; not token/dollar billing.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_learning_policy (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 256),
    daily_limit integer CHECK (daily_limit BETWEEN 0 AND 100000),
    PRIMARY KEY (namespace,user_id)
);
CREATE TABLE IF NOT EXISTS public.mammoth_learning_usage (
    namespace text NOT NULL,
    user_id text NOT NULL,
    day date NOT NULL,
    admitted bigint NOT NULL CHECK (admitted >= 0),
    PRIMARY KEY (namespace,user_id,day),
    FOREIGN KEY (namespace,user_id) REFERENCES public.mammoth_learning_policy(namespace,user_id)
);
CREATE TABLE IF NOT EXISTS public.mammoth_learning_operations (
    namespace text NOT NULL,
    user_id text NOT NULL,
    id text NOT NULL,
    route text NOT NULL,
    account_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('running','cancellation_requested','finished','failed','cancelled_at_boundary')),
    started_at text NOT NULL,
    finished_at text,
    PRIMARY KEY (namespace,user_id,id),
    FOREIGN KEY (namespace,user_id) REFERENCES public.mammoth_learning_policy(namespace,user_id)
);
CREATE INDEX IF NOT EXISTS mammoth_learning_operations_recent
    ON public.mammoth_learning_operations(namespace,user_id,started_at DESC,id DESC);
ALTER TABLE public.mammoth_learning_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_learning_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_learning_operations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_learning_policy,public.mammoth_learning_usage,public.mammoth_learning_operations
    FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mammoth_learning_policy,public.mammoth_learning_usage,public.mammoth_learning_operations
    TO service_role;
COMMIT;
