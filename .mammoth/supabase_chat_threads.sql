-- Exact owner/thread keys; tombstones fence late completions after deletion.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_chat_owners (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 256),
    PRIMARY KEY (namespace,user_id)
);
CREATE TABLE IF NOT EXISTS public.mammoth_chat_threads (
    namespace text NOT NULL,
    user_id text NOT NULL,
    thread_id text NOT NULL CHECK (length(thread_id) BETWEEN 1 AND 128),
    entry jsonb NOT NULL CHECK (jsonb_typeof(entry)='object'),
    messages jsonb NOT NULL CHECK (jsonb_typeof(messages)='array' AND jsonb_array_length(messages)<=120),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision>0),
    deleted boolean NOT NULL DEFAULT false,
    PRIMARY KEY (namespace,user_id,thread_id),
    FOREIGN KEY(namespace,user_id) REFERENCES public.mammoth_chat_owners(namespace,user_id),
    CHECK ((deleted AND entry='{}'::jsonb AND messages='[]'::jsonb)
        OR (NOT deleted AND entry ? 'id' AND entry->>'id'=thread_id))
);
ALTER TABLE public.mammoth_chat_owners ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_chat_threads ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_chat_owners,public.mammoth_chat_threads FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mammoth_chat_owners,public.mammoth_chat_threads TO service_role;
COMMIT;
