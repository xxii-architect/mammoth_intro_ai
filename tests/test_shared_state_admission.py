import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from mammoth_os.shared_state import JsonStateStore, StateConflict, StateUnavailable, state_session
from mammoth_os.tenant_admission import CombinedLedger, TenantLedger
from mammoth_os.runtime_ledger import RuntimeLedger, RuntimeLimitReached, ledger_context
from mammoth_os.llm_completion import Completion, complete


ROOT = Path(__file__).resolve().parents[1]


def test_local_conflicts_append_merge_and_corruption(tmp_path):
    store = JsonStateStore(tmp_path)
    path = tmp_path / "notes.json"
    with state_session():
        store.write(path, [{"id": "a", "text": "old"}])
    with state_session():
        first = store.read(path, [])
        with state_session():
            second = store.read(path, [])
            second.append({"id": "b", "text": "second"})
            store.write(path, second)
        first.append({"id": "c", "text": "first"})
        store.write(path, first)
    with state_session():
        first = store.read(path, [])
        assert [item["id"] for item in first] == ["a", "b", "c"]
        with state_session():
            second = store.read(path, [])
            second[0]["text"] = "winner"
            store.write(path, second)
        first[0]["text"] = "stale"
        with pytest.raises(StateConflict):
            store.write(path, first)
    assert json.loads(path.read_text())[0]["text"] == "winner"
    path.write_text("{", encoding="utf-8")
    with state_session(), pytest.raises(StateUnavailable, match="corrupt"):
        store.read(path, [])
    assert path.read_text() == "{"


def test_strict_learner_updates_and_retention_do_not_merge_past_bounds(tmp_path):
    store = JsonStateStore(tmp_path)
    path = tmp_path / "learner.json"
    with state_session():
        store.write(path, {"a": 0, "b": 0})
    with state_session():
        first = store.read(path, {})
        with state_session():
            second = store.read(path, {})
            second["b"] = 1
            store.write(path, second, strict=True)
        first["a"] = 1
        with pytest.raises(StateConflict):
            store.write(path, first, strict=True)
    path = tmp_path / "bounded.json"
    with state_session():
        store.write(path, [{"id": "a"}, {"id": "b"}])
    with state_session():
        store.read(path, [])
        with state_session():
            store.read(path, [])
            store.write(path, [{"id": "b"}, {"id": "c"}])
        with pytest.raises(StateConflict, match="retention"):
            store.write(path, [{"id": "b"}, {"id": "d"}])
    assert len(json.loads(path.read_text())) == 2


def test_inherited_request_contexts_keep_independent_read_snapshots(tmp_path):
    store = JsonStateStore(tmp_path)
    path = tmp_path / "notes.json"
    with state_session():
        store.write(path, [{"id": "original"}])
        first_context, second_context = copy_context(), copy_context()
        first = first_context.run(store.read, path, [])
        second = second_context.run(store.read, path, [])
        second.append({"id": "second"})
        second_context.run(store.write, path, second)
        first.append({"id": "first"})
        first_context.run(store.write, path, first)
    assert [row["id"] for row in json.loads(path.read_text())] == ["original", "second", "first"]


def test_process_appends_preserve_every_record(tmp_path):
    code = """
import sys,time
from pathlib import Path
from mammoth_os.shared_state import JsonStateStore,state_session
root=Path(sys.argv[1])
with state_session():
 store=JsonStateStore(root)
 rows=store.read(root/'notes.json',[])
 print('read',flush=True)
 input()
 rows.append({'id':sys.argv[2]})
 store.write(root/'notes.json',rows)
"""
    children = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path), str(i)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for i in range(6)]
    try:
        for child in children:
            assert child.stdout.readline().strip() == "read"
        for child in children:
            child.stdin.write("\n")
            child.stdin.flush()
        for child in children:
            _, stderr = child.communicate(timeout=30)
            assert child.returncode == 0, stderr
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
    assert {row["id"] for row in json.loads((tmp_path / "notes.json").read_text())} == set(map(str, range(6)))


def test_legacy_approval_is_claimed_before_side_effects(tmp_path, monkeypatch):
    import api_server

    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path)
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps([{"id": "a", "status": "pending", "operation": "fixture"}]))
    calls = []

    def execute(record):
        assert json.loads(path.read_text())[0]["status"] == "executing"
        calls.append(record["id"])
        raise RuntimeError("Simulated worker loss after side effect")

    monkeypatch.setattr(api_server, "_execute_approval_record", execute)
    with state_session(), pytest.raises(RuntimeError, match="worker loss"):
        api_server._approve_record("a")
    with state_session(), pytest.raises(StateConflict, match="claimed"):
        api_server._approve_record("a")
    with state_session(), pytest.raises(StateConflict, match="discarded"):
        api_server._delete_approval_record("a")
    assert calls == ["a"]


@pytest.fixture(scope="module")
def postgres():
    container = os.environ.get("MAMMOTH_TEST_POSTGRES_CONTAINER")
    if not container:
        if os.environ.get("MAMMOTH_REQUIRE_POSTGRES_TESTS") == "1":
            pytest.fail("A dedicated PostgreSQL test container is required.")
        pytest.skip("Set MAMMOTH_TEST_POSTGRES_CONTAINER to run real PostgreSQL integration tests.")
    database = "mammoth_admission_" + uuid.uuid4().hex

    def sql(statement, *, db=database, check=True):
        result = subprocess.run(
            ["docker", "exec", container, "psql", "-U", "postgres", "-d", db,
             "-X", "-q", "-A", "-t", "--set=ON_ERROR_STOP=1", "-c", statement],
            text=True, capture_output=True, timeout=30,
        )
        if check:
            assert result.returncode == 0, result.stderr
        return result.stdout.strip() if check else result

    sql(f"CREATE DATABASE {database}", db="postgres")
    try:
        sql("""
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role BYPASSRLS; END IF;
END $$;
CREATE SCHEMA auth;
CREATE TABLE auth.users(id uuid PRIMARY KEY,email text,raw_user_meta_data jsonb DEFAULT '{}');
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS $$ SELECT NULL::uuid $$;
""")
        for migration in ("supabase_tenant_auth.sql", "supabase_runtime_state.sql", "supabase_tenant_admission.sql"):
            sql((ROOT / ".mammoth" / migration).read_text(encoding="utf-8"))
        # Reapplication is safe and does not erase existing operational records.
        sql((ROOT / ".mammoth" / "supabase_runtime_state.sql").read_text())
        sql((ROOT / ".mammoth" / "supabase_tenant_admission.sql").read_text())
        yield sql
    finally:
        sql(f"DROP DATABASE {database} WITH (FORCE)", db="postgres")


def rpc_for(sql):
    def literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, (dict, list)):
            return "'" + json.dumps(value).replace("'", "''") + "'::jsonb"
        return "'" + value.replace("'", "''") + "'"

    def rpc(name, params):
        assert name.startswith("mammoth_") and name.replace("_", "").isalnum()
        arguments = ",".join(f"{key}=>{literal(value)}" for key, value in params.items())
        return json.loads(sql(f"SET ROLE service_role; SELECT public.{name}({arguments});"))
    return rpc


@pytest.fixture
def tenant(postgres):
    owner, member, outsider, tenant_id = [str(uuid.uuid4()) for _ in range(4)]
    postgres(f"""
INSERT INTO auth.users(id) VALUES('{owner}'),('{member}'),('{outsider}');
INSERT INTO public.tenants(id,slug,name,owner_user_id) VALUES('{tenant_id}','{tenant_id}','Fixture','{owner}');
INSERT INTO public.workspace_memberships(tenant_id,user_id,role) VALUES
 ('{tenant_id}','{owner}','owner'),('{tenant_id}','{member}','member');
INSERT INTO public.mammoth_runtime_prices VALUES
 ('fixture','fixture-v1','test-only-v1',1000000,2000000,'synthetic deterministic fixture',now()+interval '1 day')
 ON CONFLICT(provider,model) DO UPDATE SET expires_at=excluded.expires_at;
""")
    rpc = rpc_for(postgres)
    return (TenantLedger(owner, tenant_id, rpc=rpc), TenantLedger(member, tenant_id, rpc=rpc),
            TenantLedger(outsider, tenant_id, rpc=rpc), postgres)


def test_postgres_shared_state_cas_and_roles(postgres, tmp_path, monkeypatch):
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", "fixture")
    rpc = rpc_for(postgres)
    store = JsonStateStore(tmp_path, rpc)
    path = tmp_path / (uuid.uuid4().hex + ".json")
    with state_session():
        rows = store.read(path, [])
        with state_session():
            other = store.read(path, [])
            other.append({"id": "second"})
            store.write(path, other)
        rows.append({"id": "first"})
        store.write(path, rows)
    assert store.read(path, []) == [{"id": "second"}, {"id": "first"}]
    key = "fixture/" + uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: rpc("mammoth_state_cas", {
            "p_key": key, "p_revision": 0, "p_payload": {"id": str(index)},
        }), range(12)))
    assert sum(result["saved"] is True for result in results) == 1
    assert rpc("mammoth_state_read", {"p_key": key})["revision"] == 1
    for role in ("anon", "authenticated"):
        for statement in (
            "SELECT public.mammoth_state_read('fixture/private.json')",
            "SELECT * FROM public.mammoth_runtime_state",
            "SELECT * FROM public.mammoth_tenant_runtime_attempts",
            "SELECT public.mammoth_runtime_memberships(NULL)",
        ):
            result = postgres(f"SET ROLE {role}; {statement}", check=False)
            assert result.returncode != 0 and "permission denied" in result.stderr


def test_postgres_tenant_access_and_policy_validation(tenant):
    owner, member, outsider, sql = tenant
    assert owner.snapshot()["attempts"] == 0
    with pytest.raises(RuntimeLimitReached, match="admin_required"):
        member.set_limits(100, 100)
    with pytest.raises(RuntimeLimitReached, match="access_denied"):
        outsider.snapshot()
    with pytest.raises(RuntimeLimitReached, match="access_denied"):
        outsider.reserve("fixture", "fixture-v1", 10, input_tokens=5, output_tokens=5)
    for value in (True, -1, 1.5, "12", 1_000_000_000_001):
        with pytest.raises(ValueError):
            owner.set_limits(None, value)
    owner.set_limits(0, 0)
    with pytest.raises(RuntimeLimitReached, match="token_limit"):
        member.reserve("fixture", "fixture-v1", 10, input_tokens=5, output_tokens=5)
    sql(f"UPDATE public.workspace_memberships SET role='viewer' WHERE tenant_id='{owner.tenant_id}' AND user_id='{member.user_id}'")
    assert member.snapshot()["attempts"] == 0
    with pytest.raises(RuntimeLimitReached, match="access_denied"):
        member.reserve("fixture", "fixture-v1", 10, input_tokens=5, output_tokens=5)
    sql(f"UPDATE public.workspace_memberships SET status='revoked' WHERE tenant_id='{owner.tenant_id}' AND user_id='{member.user_id}'")
    with pytest.raises(RuntimeLimitReached, match="access_denied"):
        member.snapshot()


def test_postgres_concurrent_tenant_dollar_reservations(tenant):
    owner, member, _, _ = tenant
    owner.set_limits(None, 45)  # Each synthetic 5-in/5-out allowance costs 15 microUSD.

    def reserve(_):
        try:
            return member.reserve("fixture", "fixture-v1", 10, input_tokens=5, output_tokens=5)
        except RuntimeLimitReached as exc:
            assert "dollar_limit" in str(exc)
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        attempts = [item for item in pool.map(reserve, range(12)) if item]
    assert len(attempts) == 3
    snapshot = owner.snapshot()
    assert snapshot["attempts"] == 3 and snapshot["estimated_usd_micros"] == 45
    assert snapshot["unknown_attempts"] == 3 and snapshot["invoice_verified"] is False
    member.finish(attempts[0], usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    member.finish(attempts[0], usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    assert owner.snapshot()["estimated_usd_micros"] == 33
    with pytest.raises(StateUnavailable, match="settlement"):
        member.finish(attempts[0], usage={"total_tokens": 1})
    member.finish(attempts[1], failed=True)
    assert owner.snapshot()["estimated_usd_micros"] == 33
    identity = member.reserve("fixture", "fixture-v1", 6, input_tokens=2, output_tokens=4)
    member.finish(identity, usage={"total_tokens": 20})
    assert owner.snapshot()["estimated_usd_micros"] == 73
    with pytest.raises(RuntimeLimitReached, match="dollar_limit"):
        owner.reserve("fixture", "fixture-v1", 2, input_tokens=1, output_tokens=1)


def test_postgres_missing_expired_prices_and_unknown_accounting(tenant):
    owner, member, _, sql = tenant
    owner.set_limits(None, 100)
    with pytest.raises(RuntimeLimitReached, match="price_or_prior_cost_unknown"):
        member.reserve("unpriced", "model", 10, input_tokens=5, output_tokens=5)
    owner.set_limits(None, None)
    identity = member.reserve("unpriced", "model", 10, input_tokens=5, output_tokens=5)
    member.finish(identity, usage={"total_tokens": 4})
    assert owner.snapshot()["unknown_price_attempts"] == 1
    owner.set_limits(None, 100)
    with pytest.raises(RuntimeLimitReached, match="prior_cost_unknown"):
        member.reserve("fixture", "fixture-v1", 10, input_tokens=5, output_tokens=5)
    sql("UPDATE public.mammoth_runtime_prices SET expires_at=now()-interval '1 second'")
    # Separate tenant isolates the expired-price case from an existing unknown cost.
    sql(f"DELETE FROM public.mammoth_tenant_runtime_attempts WHERE tenant_id='{owner.tenant_id}'")
    with pytest.raises(RuntimeLimitReached, match="price_or_prior_cost_unknown"):
        member.reserve("fixture", "fixture-v1", 10, input_tokens=5, output_tokens=5)


def test_postgres_completion_wiring_and_additive_private_cap(tenant, tmp_path):
    owner, member, _, _ = tenant
    owner.set_limits(10000, 10000)
    private = RuntimeLedger(tmp_path / "private.sqlite3")
    ledger = CombinedLedger(private, member)

    class Client:
        model = "fixture-v1"
        calls = 0

        async def generate_completion(self, prompt, **kwargs):
            self.calls += 1
            return Completion("ok", usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})

    # The leaf provider label is derived honestly from its adapter name.
    client = Client()
    owner.set_limits(0, None)
    with ledger_context(ledger), pytest.raises(RuntimeLimitReached):
        asyncio.run(complete(client, "hello", max_tokens=8))
    assert client.calls == 0 and private.snapshot()["attempts"] == 0
    owner.set_limits(10000, None)
    with ledger_context(ledger):
        assert asyncio.run(complete(client, "hello", max_tokens=8)).text == "ok"
    assert owner.snapshot()["reported_tokens"] == 2 and private.snapshot()["reported_tokens"] == 2
    private.set_limit(0)
    with ledger_context(ledger), pytest.raises(RuntimeLimitReached):
        asyncio.run(complete(client, "hello", max_tokens=8))
    assert client.calls == 1 and owner.snapshot()["attempts"] == 1


def test_loaded_tenant_routes_use_membership_not_global_admin(tenant, monkeypatch, tmp_path):
    import api_server
    import mammoth_os.tenant_admission as admission
    from fastapi.testclient import TestClient

    owner, member, outsider, sql = tenant
    monkeypatch.setattr(admission, "service_rpc", rpc_for(sql))
    monkeypatch.setenv("MAMMOTH_USAGE_BACKEND", "supabase")
    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path)
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": token, "email": "", "is_admin": token == outsider.user_id,
    })
    with TestClient(api_server.app) as client:
        owner_headers = {"Authorization": f"Bearer {owner.user_id}"}
        member_headers = {"Authorization": f"Bearer {member.user_id}"}
        outsider_headers = {"Authorization": f"Bearer {outsider.user_id}"}
        assert client.get("/api/runtime/tenants").status_code == 401
        assert client.get("/api/runtime/tenants", headers=owner_headers).json()["tenants"][0]["tenant_id"] == owner.tenant_id
        body = {"tenant_id": owner.tenant_id, "daily_token_limit": 0, "daily_usd_limit_micros": 1}
        assert client.put("/api/runtime/tenant-usage/policy", headers=owner_headers, json=body).status_code == 200
        assert client.put("/api/runtime/tenant-usage/policy", headers=member_headers, json=body).status_code == 403
        assert client.put("/api/runtime/tenant-usage/policy", headers=outsider_headers, json=body).status_code == 403
        assert client.get(f"/api/runtime/tenant-usage?tenant_id={owner.tenant_id}", headers=outsider_headers).status_code == 403
        invalid = {**owner_headers, "X-Mammoth-Tenant-ID": "../foreign"}
        assert client.get("/api/runtime/tenants", headers=invalid).status_code == 400
        assert client.put("/api/runtime/tenant-usage/policy", headers=owner_headers, json={**body, "daily_token_limit": True}).status_code == 400
    assert sql(f"SELECT count(*) FROM public.audit_events WHERE tenant_id='{owner.tenant_id}' AND action='runtime_admission_policy_changed'") == "1"


def test_storage_errors_and_declared_replicas_are_explicit(tmp_path, monkeypatch):
    import api_server
    from fastapi.testclient import TestClient

    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path)
    monkeypatch.setattr(api_server, "NOTES_FILE", tmp_path / "notes.json")
    (tmp_path / "notes.json").write_text("{")
    with TestClient(api_server.app) as client:
        response = client.get("/api/notes")
        assert response.status_code == 503 and response.json()["code"] == "storage_unavailable"
        assert (tmp_path / "notes.json").read_text() == "{"
        monkeypatch.setenv("MAMMOTH_REPLICA_COUNT", "2")
        response = client.get("/api/runtime/usage")
        assert response.status_code == 503 and response.json()["code"] == "storage_unavailable"


def test_hosted_preflight_cannot_certify_a_missing_service(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import scripts.quality.check_hosted_owner_container as probe

    calls = []

    def command(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="0\n")

    monkeypatch.setattr(probe.subprocess, "run", command)
    receipt = probe.inspect_host(tmp_path, "configured", "fixture-revision")
    assert receipt["status"] == "not_verified"
    assert receipt["reason"] == "live_service_not_found"
    assert receipt["deployment_modified"] is False and receipt["images_pulled"] is False
    assert calls == [["systemctl", "show", "mammothos", "--property=MainPID", "--value"]]


def test_explicit_migration_never_overwrites_a_destination(tmp_path, monkeypatch):
    import scripts.migrate_shared_state as migration

    path = tmp_path / "notes.json"
    path.write_text('[{"id":"fixture"}]')
    monkeypatch.setattr(migration, "service_rpc", lambda *args: {"saved": False})
    monkeypatch.setattr(sys, "argv", ["migrate", "import", "--key", "fixture/notes.json",
                                    "--file", str(path), "--confirm-quiesced"])
    with pytest.raises(RuntimeError, match="already exists"):
        migration.main()
    assert json.loads(path.read_text()) == [{"id": "fixture"}]
