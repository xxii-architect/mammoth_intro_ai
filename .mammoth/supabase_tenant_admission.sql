-- Apply after supabase_tenant_auth.sql. Estimates are never invoices.
BEGIN;
CREATE TABLE IF NOT EXISTS public.mammoth_tenant_runtime_policy (
    tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE CASCADE,
    daily_tokens bigint CHECK (daily_tokens BETWEEN 0 AND 1000000000),
    daily_usd_micros bigint CHECK (daily_usd_micros BETWEEN 0 AND 1000000000000),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS public.mammoth_runtime_prices (
    provider text NOT NULL,
    model text NOT NULL,
    version text NOT NULL,
    input_micros_per_million bigint NOT NULL CHECK (input_micros_per_million >= 0),
    output_micros_per_million bigint NOT NULL CHECK (output_micros_per_million >= 0),
    source text NOT NULL CHECK (length(source) > 0),
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (provider, model)
);
CREATE TABLE IF NOT EXISTS public.mammoth_tenant_runtime_attempts (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(id),
    day date NOT NULL DEFAULT (clock_timestamp() AT TIME ZONE 'UTC')::date,
    provider text NOT NULL,
    model text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','completed','completed_unknown','failed_unknown')),
    reserved_tokens bigint NOT NULL CHECK (reserved_tokens > 0),
    reported_tokens bigint,
    reserved_usd_micros bigint,
    accounted_usd_micros bigint,
    price jsonb,
    settlement jsonb
);
CREATE INDEX IF NOT EXISTS mammoth_tenant_attempt_day ON public.mammoth_tenant_runtime_attempts(tenant_id, day);
ALTER TABLE public.mammoth_tenant_runtime_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_runtime_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mammoth_tenant_runtime_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mammoth_tenant_runtime_policy, public.mammoth_runtime_prices,
    public.mammoth_tenant_runtime_attempts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.mammoth_tenant_runtime_policy, public.mammoth_runtime_prices,
    public.mammoth_tenant_runtime_attempts TO service_role;

CREATE OR REPLACE FUNCTION public.mammoth_runtime_memberships(p_user uuid)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT jsonb_build_object('tenants', coalesce(jsonb_agg(jsonb_build_object(
        'tenant_id', m.tenant_id, 'name', t.name, 'role', m.role) ORDER BY t.name, m.tenant_id), '[]'::jsonb))
    FROM public.workspace_memberships m JOIN public.tenants t ON t.id=m.tenant_id
    WHERE m.user_id=p_user AND m.status='active'
$$;

CREATE OR REPLACE FUNCTION public.mammoth_runtime_policy(
    p_user uuid, p_tenant uuid, p_tokens bigint, p_usd_micros bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.workspace_memberships
        WHERE tenant_id=p_tenant AND user_id=p_user AND status='active' AND role IN ('owner','admin')) THEN
        RETURN jsonb_build_object('error','tenant_admin_required');
    END IF;
    INSERT INTO public.mammoth_tenant_runtime_policy(tenant_id, daily_tokens, daily_usd_micros)
        VALUES(p_tenant,p_tokens,p_usd_micros)
        ON CONFLICT(tenant_id) DO UPDATE SET daily_tokens=p_tokens,daily_usd_micros=p_usd_micros,
            updated_at=clock_timestamp();
    INSERT INTO public.audit_events(tenant_id,actor_user_id,action,resource_type,resource_id,metadata)
        VALUES(p_tenant,p_user,'runtime_admission_policy_changed','tenant_runtime_policy',p_tenant::text,
            jsonb_build_object('daily_tokens',p_tokens,'daily_usd_micros',p_usd_micros,'invoice_verified',false));
    RETURN jsonb_build_object('saved',true);
END $$;

CREATE OR REPLACE FUNCTION public.mammoth_runtime_reserve(
    p_user uuid, p_tenant uuid, p_id uuid, p_provider text, p_model text,
    p_input bigint, p_output bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE policy public.mammoth_tenant_runtime_policy;
    rate public.mammoth_runtime_prices;
    used_tokens numeric; used_usd numeric; unknown_prices bigint; reserved_usd bigint;
    today date := (clock_timestamp() AT TIME ZONE 'UTC')::date;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.workspace_memberships
        WHERE tenant_id=p_tenant AND user_id=p_user AND status='active' AND role IN ('owner','admin','member')) THEN
        RETURN jsonb_build_object('error','tenant_access_denied');
    END IF;
    IF p_input IS NULL OR p_output IS NULL OR p_input < 0 OR p_output < 1
        OR p_input > 1000000000 OR p_output > 1000000000 THEN
        RAISE EXCEPTION 'Invalid token allowance';
    END IF;
    INSERT INTO public.mammoth_tenant_runtime_policy(tenant_id) VALUES(p_tenant) ON CONFLICT DO NOTHING;
    SELECT * INTO policy FROM public.mammoth_tenant_runtime_policy WHERE tenant_id=p_tenant FOR UPDATE;
    IF EXISTS (SELECT 1 FROM public.mammoth_tenant_runtime_attempts WHERE id=p_id) THEN
        RETURN jsonb_build_object('error','attempt_already_reserved');
    END IF;
    SELECT * INTO rate FROM public.mammoth_runtime_prices
        WHERE provider=p_provider AND model=p_model AND expires_at > clock_timestamp();
    IF FOUND THEN
        reserved_usd := ceil((p_input::numeric*rate.input_micros_per_million
            +p_output::numeric*rate.output_micros_per_million)/1000000);
    END IF;
    SELECT coalesce(sum(coalesce(reported_tokens,reserved_tokens)),0),
        coalesce(sum(coalesce(accounted_usd_micros,reserved_usd_micros)),0),
        count(*) FILTER (WHERE coalesce(accounted_usd_micros,reserved_usd_micros) IS NULL)
        INTO used_tokens,used_usd,unknown_prices
        FROM public.mammoth_tenant_runtime_attempts WHERE tenant_id=p_tenant AND day=today;
    IF policy.daily_tokens IS NOT NULL AND used_tokens+p_input+p_output > policy.daily_tokens THEN
        RETURN jsonb_build_object('error','tenant_token_limit');
    END IF;
    IF policy.daily_usd_micros IS NOT NULL AND (reserved_usd IS NULL OR unknown_prices > 0) THEN
        RETURN jsonb_build_object('error','price_or_prior_cost_unknown');
    END IF;
    IF policy.daily_usd_micros IS NOT NULL AND used_usd+reserved_usd > policy.daily_usd_micros THEN
        RETURN jsonb_build_object('error','tenant_estimated_dollar_limit');
    END IF;
    INSERT INTO public.mammoth_tenant_runtime_attempts(
        id,tenant_id,user_id,day,provider,model,reserved_tokens,reserved_usd_micros,price)
        VALUES(p_id,p_tenant,p_user,today,p_provider,p_model,p_input+p_output,reserved_usd,
            CASE WHEN reserved_usd IS NOT NULL THEN to_jsonb(rate) ELSE NULL END);
    RETURN jsonb_build_object('admitted',true,'attempt_id',p_id,'reserved_usd_micros',reserved_usd);
END $$;

CREATE OR REPLACE FUNCTION public.mammoth_runtime_finish(
    p_user uuid, p_tenant uuid, p_id uuid, p_usage jsonb, p_failed boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE attempt public.mammoth_tenant_runtime_attempts;
    total bigint; input_tokens bigint; output_tokens bigint; cost bigint;
    final_settlement jsonb := jsonb_build_object('usage',p_usage,'failed',p_failed);
BEGIN
    -- Same lock order as reserve; serializes settlement against new admissions.
    PERFORM 1 FROM public.mammoth_tenant_runtime_policy WHERE tenant_id=p_tenant FOR UPDATE;
    SELECT * INTO attempt FROM public.mammoth_tenant_runtime_attempts
        WHERE id=p_id AND tenant_id=p_tenant AND user_id=p_user FOR UPDATE;
    IF NOT FOUND THEN RETURN jsonb_build_object('error','attempt_not_found'); END IF;
    IF attempt.status <> 'pending' THEN
        RETURN jsonb_build_object('saved',attempt.settlement=final_settlement,'replayed',true);
    END IF;
    IF NOT p_failed THEN
        IF jsonb_typeof(p_usage->'total_tokens')='number' AND (p_usage->>'total_tokens') ~ '^[0-9]{1,12}$' THEN
            total := (p_usage->>'total_tokens')::bigint;
        END IF;
        IF jsonb_typeof(p_usage->'prompt_tokens')='number' AND (p_usage->>'prompt_tokens') ~ '^[0-9]{1,12}$'
            AND jsonb_typeof(p_usage->'completion_tokens')='number' AND (p_usage->>'completion_tokens') ~ '^[0-9]{1,12}$' THEN
            input_tokens := (p_usage->>'prompt_tokens')::bigint;
            output_tokens := (p_usage->>'completion_tokens')::bigint;
            total := greatest(coalesce(total,0),input_tokens+output_tokens);
        END IF;
        IF total = 0 THEN total := NULL; END IF;
        IF total IS NOT NULL AND attempt.price IS NOT NULL THEN
            IF input_tokens IS NOT NULL AND output_tokens IS NOT NULL AND input_tokens+output_tokens=total THEN
                cost := ceil((input_tokens::numeric*(attempt.price->>'input_micros_per_million')::bigint
                    +output_tokens::numeric*(attempt.price->>'output_micros_per_million')::bigint)/1000000);
            ELSE
                cost := greatest(attempt.reserved_usd_micros,ceil(total::numeric*greatest(
                    (attempt.price->>'input_micros_per_million')::bigint,
                    (attempt.price->>'output_micros_per_million')::bigint)/1000000));
            END IF;
        END IF;
    END IF;
    UPDATE public.mammoth_tenant_runtime_attempts SET finished_at=clock_timestamp(),
        reported_tokens=total,accounted_usd_micros=cost,settlement=final_settlement,
        status=CASE WHEN p_failed THEN 'failed_unknown' WHEN total IS NULL THEN 'completed_unknown' ELSE 'completed' END
        WHERE id=p_id;
    RETURN jsonb_build_object('saved',true);
END $$;

CREATE OR REPLACE FUNCTION public.mammoth_runtime_usage(p_user uuid, p_tenant uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE policy public.mammoth_tenant_runtime_policy; result jsonb;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.workspace_memberships
        WHERE tenant_id=p_tenant AND user_id=p_user AND status='active') THEN
        RETURN jsonb_build_object('error','tenant_access_denied');
    END IF;
    SELECT * INTO policy FROM public.mammoth_tenant_runtime_policy WHERE tenant_id=p_tenant;
    SELECT jsonb_build_object('attempts',count(*),
        'reported_tokens',coalesce(sum(reported_tokens),0),
        'unresolved_reserved_tokens',coalesce(sum(reserved_tokens) FILTER (WHERE reported_tokens IS NULL),0),
        'unknown_attempts',count(*) FILTER (WHERE reported_tokens IS NULL),
        'estimated_usd_micros',coalesce(sum(coalesce(accounted_usd_micros,reserved_usd_micros)),0),
        'unknown_price_attempts',count(*) FILTER (WHERE coalesce(accounted_usd_micros,reserved_usd_micros) IS NULL))
        INTO result FROM public.mammoth_tenant_runtime_attempts
        WHERE tenant_id=p_tenant AND day=(clock_timestamp() AT TIME ZONE 'UTC')::date;
    RETURN result || jsonb_build_object(
        'contract','mammoth.tenant-usage.v1','tenant_id',p_tenant,
        'day_utc',(clock_timestamp() AT TIME ZONE 'UTC')::date,
        'daily_token_limit',policy.daily_tokens,'daily_usd_limit_micros',policy.daily_usd_micros,
        'invoice_verified',false,'cost_basis','versioned_estimate_not_invoice',
        'coverage','hosted_completion_admission_not_all_paid_services');
END $$;

REVOKE ALL ON FUNCTION public.mammoth_runtime_memberships(uuid),
    public.mammoth_runtime_policy(uuid,uuid,bigint,bigint),
    public.mammoth_runtime_reserve(uuid,uuid,uuid,text,text,bigint,bigint),
    public.mammoth_runtime_finish(uuid,uuid,uuid,jsonb,boolean),
    public.mammoth_runtime_usage(uuid,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.mammoth_runtime_memberships(uuid),
    public.mammoth_runtime_policy(uuid,uuid,bigint,bigint),
    public.mammoth_runtime_reserve(uuid,uuid,uuid,text,text,bigint,bigint),
    public.mammoth_runtime_finish(uuid,uuid,uuid,jsonb,boolean),
    public.mammoth_runtime_usage(uuid,uuid) TO service_role;
COMMIT;
