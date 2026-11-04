-- Atomic private document metadata, raw bytes, indexed sections and review state.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_document_owners (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 256),
    PRIMARY KEY (namespace,user_id)
);
CREATE TABLE IF NOT EXISTS public.mammoth_documents (
    namespace text NOT NULL,
    user_id text NOT NULL,
    file_id text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('chat','atlas')),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    raw_bytes bytea NOT NULL,
    chunks jsonb NOT NULL CHECK (jsonb_typeof(chunks) = 'array'),
    stored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (namespace,user_id,file_id),
    UNIQUE (namespace,user_id,file_id,scope),
    FOREIGN KEY (namespace,user_id) REFERENCES public.mammoth_document_owners(namespace,user_id),
    CHECK (payload ?& ARRAY['file_id','scope','size']),
    CHECK (payload->>'file_id' = file_id AND payload->>'scope' = scope),
    CHECK ((payload->>'size')::bigint = octet_length(raw_bytes)),
    CHECK (NOT (payload ? 'path'))
);
CREATE TABLE IF NOT EXISTS public.mammoth_document_reviews (
    namespace text NOT NULL,
    user_id text NOT NULL,
    id text NOT NULL,
    file_id text NOT NULL,
    scope text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    stored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (namespace,user_id,id),
    FOREIGN KEY (namespace,user_id,file_id,scope)
        REFERENCES public.mammoth_documents(namespace,user_id,file_id,scope) ON DELETE CASCADE,
    CHECK (payload ?& ARRAY['id','file_id','scope']),
    CHECK (payload->>'id' = id AND payload->>'file_id' = file_id AND payload->>'scope' = scope)
);
CREATE INDEX IF NOT EXISTS mammoth_documents_recent
    ON public.mammoth_documents(namespace,user_id,stored_at DESC,file_id);
ALTER TABLE public.mammoth_document_owners ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_document_reviews ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_document_owners,public.mammoth_documents,public.mammoth_document_reviews
    FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mammoth_document_owners,public.mammoth_documents,public.mammoth_document_reviews
    TO service_role;
COMMIT;
