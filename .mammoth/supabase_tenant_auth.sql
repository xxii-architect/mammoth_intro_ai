-- MammothOS production tenant/auth layer
-- Run this in Supabase SQL Editor.
-- Purpose:
--  - model tenant ownership and membership
--  - make public vs private data explicit
--  - bootstrap the current user as tenant owner/admin
--  - provide billing warning surfaces without placeholder data

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Public content / marketing layer
CREATE TABLE IF NOT EXISTS public.public_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT,
    seo_meta JSONB DEFAULT '{}'::jsonb,
    published BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.public_pages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public pages are readable by everyone" ON public.public_pages;
CREATE POLICY "Public pages are readable by everyone"
    ON public.public_pages
    FOR SELECT
    USING (published = true);

-- Tenant root
CREATE TABLE IF NOT EXISTS public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    owner_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    billing_status TEXT NOT NULL DEFAULT 'trial',
    plan_tier TEXT NOT NULL DEFAULT 'pro',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Tenant owners/admins can read their tenant" ON public.tenants;
CREATE POLICY "Tenant owners/admins can read their tenant"
    ON public.tenants
    FOR SELECT
    USING (
        owner_user_id = auth.uid()
        OR EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = tenants.id
              AND wm.user_id = auth.uid()
              AND wm.role IN ('owner', 'admin')
        )
    );

DROP POLICY IF EXISTS "Tenant owner can update tenant" ON public.tenants;
CREATE POLICY "Tenant owner can update tenant"
    ON public.tenants
    FOR UPDATE
    USING (owner_user_id = auth.uid());

-- User profile snapshot
CREATE TABLE IF NOT EXISTS public.app_users (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    global_role TEXT NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.app_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read their own profile" ON public.app_users;
CREATE POLICY "Users can read their own profile"
    ON public.app_users
    FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update their own profile" ON public.app_users;
CREATE POLICY "Users can update their own profile"
    ON public.app_users
    FOR UPDATE
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Service role full access to app_users" ON public.app_users;
CREATE POLICY "Service role full access to app_users"
    ON public.app_users
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Workspace membership
CREATE TABLE IF NOT EXISTS public.workspace_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'revoked')),
    invited_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

ALTER TABLE public.workspace_memberships ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Members can read their memberships" ON public.workspace_memberships;
CREATE POLICY "Members can read their memberships"
    ON public.workspace_memberships
    FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Tenant owners/admins can manage memberships" ON public.workspace_memberships;
CREATE POLICY "Tenant owners/admins can manage memberships"
    ON public.workspace_memberships
    FOR ALL
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships as owner_membership
            WHERE owner_membership.tenant_id = workspace_memberships.tenant_id
              AND owner_membership.user_id = auth.uid()
              AND owner_membership.role IN ('owner', 'admin')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships as owner_membership
            WHERE owner_membership.tenant_id = workspace_memberships.tenant_id
              AND owner_membership.user_id = auth.uid()
              AND owner_membership.role IN ('owner', 'admin')
        )
    );

-- Workspace account / tenant workspace container
CREATE TABLE IF NOT EXISTS public.workspace_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    owner_user_id UUID REFERENCES auth.users(id),
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.workspace_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read workspace accounts in their tenant" ON public.workspace_accounts;
CREATE POLICY "Users can read workspace accounts in their tenant"
    ON public.workspace_accounts
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = workspace_accounts.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

DROP POLICY IF EXISTS "Tenant owners/admins can manage workspace accounts" ON public.workspace_accounts;
CREATE POLICY "Tenant owners/admins can manage workspace accounts"
    ON public.workspace_accounts
    FOR ALL
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = workspace_accounts.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.role IN ('owner', 'admin')
              AND wm.status = 'active'
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = workspace_accounts.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.role IN ('owner', 'admin')
              AND wm.status = 'active'
        )
    );

-- Billing + plan limits
CREATE TABLE IF NOT EXISTS public.plan_limits (
    plan_tier TEXT PRIMARY KEY,
    request_limit INTEGER NOT NULL,
    token_limit BIGINT NOT NULL,
    seat_limit INTEGER NOT NULL,
    warning_threshold NUMERIC(5,2) NOT NULL DEFAULT 0.70,
    hard_cap BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.plan_limits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Plan limits readable by authenticated users" ON public.plan_limits;
CREATE POLICY "Plan limits readable by authenticated users"
    ON public.plan_limits
    FOR SELECT
    USING (auth.uid() IS NOT NULL);

INSERT INTO public.plan_limits (plan_tier, request_limit, token_limit, seat_limit, warning_threshold, hard_cap)
VALUES
    ('explorer', 2500, 200000, 1, 0.70, false),
    ('pro', 10000, 1000000, 5, 0.70, false),
    ('enterprise', 50000, 10000000, 50, 0.80, true)
ON CONFLICT (plan_tier) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    workspace_account_id UUID REFERENCES public.workspace_accounts(id) ON DELETE SET NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    model TEXT,
    request_units INTEGER NOT NULL DEFAULT 1,
    tokens_in BIGINT NOT NULL DEFAULT 0,
    tokens_out BIGINT NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Tenant members can read usage events" ON public.usage_events;
CREATE POLICY "Tenant members can read usage events"
    ON public.usage_events
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = usage_events.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

DROP POLICY IF EXISTS "Service role full access to usage events" ON public.usage_events;
CREATE POLICY "Service role full access to usage events"
    ON public.usage_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE TABLE IF NOT EXISTS public.usage_rollups_daily (
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    day DATE NOT NULL,
    request_units INTEGER NOT NULL DEFAULT 0,
    tokens_total BIGINT NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, day)
);

ALTER TABLE public.usage_rollups_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Tenant members can read usage rollups" ON public.usage_rollups_daily;
CREATE POLICY "Tenant members can read usage rollups"
    ON public.usage_rollups_daily
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = usage_rollups_daily.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

-- Audit and policy state
CREATE TABLE IF NOT EXISTS public.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES public.tenants(id) ON DELETE CASCADE,
    actor_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Tenant members can read audit log" ON public.audit_events;
CREATE POLICY "Tenant members can read audit log"
    ON public.audit_events
    FOR SELECT
    USING (
        tenant_id IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = audit_events.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

DROP POLICY IF EXISTS "Service role full access to audit_events" ON public.audit_events;
CREATE POLICY "Service role full access to audit_events"
    ON public.audit_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE TABLE IF NOT EXISTS public.policy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.policy_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public policy versions are readable" ON public.policy_versions;
CREATE POLICY "Public policy versions are readable"
    ON public.policy_versions
    FOR SELECT
    USING (true);

CREATE TABLE IF NOT EXISTS public.policy_acceptances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    policy_version TEXT NOT NULL REFERENCES public.policy_versions(version) ON DELETE CASCADE,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id, policy_version)
);

ALTER TABLE public.policy_acceptances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read their own policy acceptances" ON public.policy_acceptances;
CREATE POLICY "Users can read their own policy acceptances"
    ON public.policy_acceptances
    FOR SELECT
    USING (user_id = auth.uid());

CREATE TABLE IF NOT EXISTS public.tenant_settings (
    tenant_id UUID PRIMARY KEY REFERENCES public.tenants(id) ON DELETE CASCADE,
    developer_mode_enabled BOOLEAN NOT NULL DEFAULT false,
    entitlements_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    feature_flags_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.tenant_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Tenant members can read tenant settings" ON public.tenant_settings;
CREATE POLICY "Tenant members can read tenant settings"
    ON public.tenant_settings
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = tenant_settings.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.status = 'active'
        )
    );

DROP POLICY IF EXISTS "Owner/admin can update tenant settings" ON public.tenant_settings;
CREATE POLICY "Owner/admin can update tenant settings"
    ON public.tenant_settings
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1
            FROM public.workspace_memberships wm
            WHERE wm.tenant_id = tenant_settings.tenant_id
              AND wm.user_id = auth.uid()
              AND wm.role IN ('owner', 'admin')
              AND wm.status = 'active'
        )
    );

-- Bootstrap function: create tenant + owner membership for the current Supabase user
CREATE OR REPLACE FUNCTION public.bootstrap_tenant_for_user(
    p_name TEXT,
    p_slug TEXT,
    p_owner_user_id UUID DEFAULT auth.uid()
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_tenant_id UUID;
    v_membership_count INTEGER;
BEGIN
    IF p_owner_user_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required to bootstrap tenant';
    END IF;

    SELECT COUNT(*) INTO v_membership_count
    FROM public.workspace_memberships wm
    WHERE wm.user_id = p_owner_user_id
      AND wm.role = 'owner';

    IF v_membership_count > 0 THEN
        SELECT id INTO v_tenant_id
        FROM public.tenants
        WHERE owner_user_id = p_owner_user_id
        LIMIT 1;
        RETURN v_tenant_id;
    END IF;

    INSERT INTO public.tenants (slug, name, owner_user_id, plan_tier, billing_status)
    VALUES (p_slug, p_name, p_owner_user_id, 'pro', 'trial')
    RETURNING id INTO v_tenant_id;

    INSERT INTO public.workspace_memberships (tenant_id, user_id, role, status, invited_by)
    VALUES (v_tenant_id, p_owner_user_id, 'owner', 'active', p_owner_user_id)
    ON CONFLICT (tenant_id, user_id) DO UPDATE
    SET role = 'owner', status = 'active';

    INSERT INTO public.workspace_accounts (tenant_id, name, owner_user_id, is_active)
    VALUES (v_tenant_id, 'Primary Workspace', p_owner_user_id, true)
    ON CONFLICT DO NOTHING;

    INSERT INTO public.tenant_settings (tenant_id, developer_mode_enabled, entitlements_json, feature_flags_json)
    VALUES (
        v_tenant_id,
        false,
        '{"tier": "pro", "developer_access": false}'::jsonb,
        '{"billing_alerts": true, "usage_guardrails": true}'::jsonb
    )
    ON CONFLICT (tenant_id) DO NOTHING;

    INSERT INTO public.app_users (user_id, email, display_name, global_role)
    SELECT au.id, au.email, COALESCE(au.raw_user_meta_data ->> 'name', au.email), 'platform_admin'
    FROM auth.users au
    WHERE au.id = p_owner_user_id
    ON CONFLICT (user_id) DO UPDATE
    SET email = EXCLUDED.email,
        display_name = EXCLUDED.display_name,
        global_role = 'platform_admin';

    RETURN v_tenant_id;
END;
$$;

-- index helpers
CREATE INDEX IF NOT EXISTS idx_workspace_memberships_tenant_user ON public.workspace_memberships (tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user_role ON public.workspace_memberships (user_id, role);
CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_created_at ON public.usage_events (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_created_at ON public.audit_events (tenant_id, created_at DESC);

-- helper view: current tenant usage snapshot for the app
CREATE OR REPLACE VIEW public.tenant_usage_summary AS
SELECT
    t.id AS tenant_id,
    t.name AS tenant_name,
    t.plan_tier,
    COALESCE(SUM(ue.request_units), 0) AS request_units_used,
    COALESCE(SUM(ue.tokens_in + ue.tokens_out), 0) AS tokens_used,
    COALESCE(SUM(ue.cost_usd), 0) AS cost_usd,
    MAX(ue.created_at) AS last_usage_at
FROM public.tenants t
LEFT JOIN public.usage_events ue ON ue.tenant_id = t.id
GROUP BY t.id, t.name, t.plan_tier;

-- End of tenant/auth schema bootstrap.
