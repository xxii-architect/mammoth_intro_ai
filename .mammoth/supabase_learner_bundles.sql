-- Experimental storage primitive; not a runtime backend or a data migration.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_learner_bundles (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 256),
    state jsonb NOT NULL CHECK (jsonb_typeof(state) = 'object'),
    drafts jsonb NOT NULL CHECK (jsonb_typeof(drafts) = 'object'),
    models jsonb NOT NULL CHECK (jsonb_typeof(models) = 'object'),
    revision bigint NOT NULL CHECK (revision > 0),
    PRIMARY KEY (namespace, user_id)
);
ALTER TABLE public.mammoth_learner_bundles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_learner_bundles FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.mammoth_learner_bundles TO service_role;
CREATE TABLE IF NOT EXISTS public.mammoth_learner_operation_fences (
    namespace text NOT NULL,
    user_id text NOT NULL,
    operation_id text NOT NULL,
    fence jsonb NOT NULL CHECK (jsonb_typeof(fence) = 'object'),
    PRIMARY KEY (namespace, user_id, operation_id),
    FOREIGN KEY (namespace, user_id, operation_id)
        REFERENCES public.mammoth_learning_operations(namespace, user_id, id) ON DELETE CASCADE
);
ALTER TABLE public.mammoth_learner_operation_fences ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_learner_operation_fences FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.mammoth_learner_operation_fences TO service_role;
COMMIT;
