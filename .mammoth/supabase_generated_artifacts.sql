-- Private immutable generated DOCX bytes and ownership, never tenant-direct SQL.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_generated_owners (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    user_id text NOT NULL CHECK (length(user_id) BETWEEN 1 AND 256),
    PRIMARY KEY (namespace,user_id)
);
CREATE TABLE IF NOT EXISTS public.mammoth_generated_artifacts (
    namespace text NOT NULL CHECK (length(namespace) BETWEEN 1 AND 128),
    filename text NOT NULL CHECK (length(filename) BETWEEN 6 AND 240 AND right(filename,5) = '.docx'),
    user_id text,
    raw_bytes bytea NOT NULL CHECK (octet_length(raw_bytes) BETWEEN 1 AND 52428800),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    stored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (namespace,filename),
    FOREIGN KEY (namespace,user_id) REFERENCES public.mammoth_generated_owners(namespace,user_id)
);
CREATE INDEX IF NOT EXISTS mammoth_generated_artifacts_owner
    ON public.mammoth_generated_artifacts(namespace,user_id);
ALTER TABLE public.mammoth_generated_owners ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_generated_artifacts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_generated_owners,public.mammoth_generated_artifacts
    FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,DELETE ON public.mammoth_generated_owners,public.mammoth_generated_artifacts TO service_role;
COMMIT;
