from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from mammoth_os.learning_workspace import LEARNER_ERASURE_EXCLUDES, workspace_snapshot
from mammoth_os.learning_controls import LearningLimitReached
from mammoth_os.postgres_learning_controls import PostgresLearningControls
from mammoth_os.postgres_learner_bundle import PostgresLearnerBundle
from mammoth_os.postgres_learner_transactions import PostgresLearnerTransactions
from mammoth_os.shared_state import StateConflict, StateUnavailable
from test_postgres_run_store import postgres as postgres_fixture, stores as run_stores_fixture

postgres = postgres_fixture
stores = run_stores_fixture


@pytest.fixture
def transactions(stores):
    base, _ = stores
    store = PostgresLearnerTransactions(base.dsn, base.namespace, "owner")
    state = {
        "active_account_id": "default", "workspace_epoch": "fixture",
        "lesson_id": "lesson", "current_exercise": {"prompt": "Explain the evidence."},
        "learner_model": {"private": "cache"}, "learner_context": {"secret": "cache"},
        "account_sessions": {"default": {"learner_model": {"private": "cache"}, "topic": "preserve"},
                             "other": {"learner_model": {"other": True}}},
    }
    bundle = {"state": state, "drafts": {}, "models": {
        "default": {"user_id": "workspace:default", "mastery": {"evidence": 0.7}},
        "other": {"user_id": "workspace:other", "mastery": {"other": 0.9}},
    }}
    PostgresLearnerBundle(base.dsn, base.namespace, "owner").write(bundle, revision=0)
    return store, bundle


def raw_store(stores):
    base, _ = stores
    return PostgresLearnerBundle(base.dsn, base.namespace, "owner")


def erase(store, kind, *, revision, account):
    bundle, _ = store._store.read()
    phrase = "DELETE PRIVATE ADAPTATION" if kind == "adaptation" else "DELETE SAVED LEARNING"
    return getattr(store, f"confirm_{kind}_erasure")(
        revision=revision, account=account, confirmation=phrase,
        preview_token=store._preview_token(kind, account, revision, bundle))


def save(store, bundle, *, revision=1, account="default", draft_revision=0, exercise_key=None):
    snapshot = workspace_snapshot(bundle["state"])
    return store.save_draft(revision=revision, account=account,
                            exercise_key=exercise_key or snapshot["exercise_key"],
                            draft_revision=draft_revision,
                            values={**snapshot["values"], "lesson_response": "Private draft"},
                            saved_at="2026-01-01T00:00:00+00:00")


def test_draft_checks_state_exercise_revision_and_owner(transactions):
    store, original = transactions
    draft, revision = save(store, original)
    assert revision == 2 and draft["revision"] == 1
    assert store._store.read()[0]["drafts"]["default"]["values"]["lesson_response"] == "Private draft"
    with pytest.raises(StateConflict):
        save(store, original)
    with pytest.raises(StateConflict):
        save(store, original, revision=2, account="other")
    with pytest.raises(StateConflict):
        save(store, original, revision=2, draft_revision=0)
    with pytest.raises(StateConflict):
        save(store, original, revision=2, draft_revision=1, exercise_key="stale")
    other = PostgresLearnerTransactions(store.dsn, store.namespace, "other")
    with pytest.raises(StateConflict):
        save(other, original)
    assert other._store.read()[1] == 0


def test_learning_session_update_is_scoped_revision_bound_and_requires_live_operation(transactions, stores):
    store, original = transactions
    fields, revision = store.read_learning_session(account="default")
    assert revision == 1 and fields["topic"] == "preserve"
    assert "learner_model" not in fields and "learner_context" not in fields
    with pytest.raises(StateConflict):
        store.read_learning_session(account="other")
    with pytest.raises(StateConflict):
        PostgresLearnerTransactions(store.dsn, store.namespace, "another-owner").read_learning_session(account="default")
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    other_operation = controls.begin("/fixture", "other")
    change = {"topic": "Updated", "current_lesson": {"title": "New"}}
    for bad in ("missing", other_operation):
        with pytest.raises(StateConflict, match="operation"):
            store.update_learning_session(revision=1, account="default", operation_id=bad, changes=change)
    for invalid in ({"learner_model": {}}, {"learner_profile": {}}, {"account_sessions": {}}, {"unknown": 1}):
        with pytest.raises(ValueError):
            store.update_learning_session(revision=1, account="default", operation_id=operation, changes=invalid)
    with pytest.raises(ValueError):
        store.update_learning_session(revision=1, account="default", operation_id=operation,
                                      changes={"topic": "x"}, remove=["topic"])
    with pytest.raises(ValueError):
        store.update_learning_session(revision=1, account="default", operation_id=operation,
                                      changes={"topic": float("nan")})
    assert raw_store(stores).read() == (original, 1)
    result, revision = store.update_learning_session(
        revision=1, account="default", operation_id=operation, changes=change, remove=["lesson_id"])
    assert revision == 2 and result["topic"] == "Updated" and "lesson_id" not in result
    saved, _ = raw_store(stores).read()
    assert saved["state"]["account_sessions"]["default"]["topic"] == "Updated"
    assert saved["state"]["account_sessions"]["other"] == original["state"]["account_sessions"]["other"]
    assert saved["models"] == original["models"] and saved["drafts"] == original["drafts"]
    assert saved["state"]["learner_context"] == original["state"]["learner_context"]
    with pytest.raises(StateConflict):
        store.update_learning_session(revision=1, account="default", operation_id=operation, changes=change)
    controls.cancel(operation)
    with pytest.raises(StateConflict, match="operation"):
        store.update_learning_session(revision=2, account="default", operation_id=operation, changes=change)
    assert raw_store(stores).read() == (saved, 2)


def test_learning_session_update_cannot_restore_data_after_erasure(transactions, stores):
    store, _ = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    preview = store.preview_learning_erasure(account="default")
    store.confirm_learning_erasure(revision=1, account="default", confirmation="DELETE SAVED LEARNING",
                                   preview_token=preview["preview_token"])
    saved, _ = raw_store(stores).read()
    for revision in (1, 2):
        with pytest.raises(StateConflict):
            store.update_learning_session(revision=revision, account="default", operation_id=operation,
                                          changes={"topic": "stale"})
    assert raw_store(stores).read() == (saved, 2)


def test_learning_session_pending_erasure_and_corrupt_account_sessions_fail_closed(transactions, stores):
    store, original = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    changed = deepcopy(original)
    changed["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    raw_store(stores).write(changed, revision=1)
    with pytest.raises(StateConflict, match="pending"):
        store.update_learning_session(revision=2, account="default", operation_id=operation, changes={"topic": "x"})
    changed["state"]["account_sessions"] = {"default": "invalid"}
    raw_store(stores).write(changed, revision=2)
    with pytest.raises(StateUnavailable, match="sessions"):
        store.read_learning_session(account="default")
    assert raw_store(stores).read() == (changed, 3)


def test_learning_session_and_deletion_cannot_both_commit_same_revision(transactions):
    store, _ = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    preview = store.preview_learning_erasure(account="default")

    def update(kind):
        try:
            if kind == "save":
                store.update_learning_session(revision=1, account="default", operation_id=operation,
                                              changes={"topic": "new"})
            else:
                store.confirm_learning_erasure(revision=1, account="default", confirmation="DELETE SAVED LEARNING",
                                               preview_token=preview["preview_token"])
            return kind
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ("save", "erase")))
    assert results.count("conflict") == 1
    assert store._store.read()[1] == 2


@pytest.mark.parametrize("change", ["account", "learning", "adaptation", "reset"])
def test_operation_fences_reject_old_work_even_with_current_bundle_revision(transactions, stores, change):
    store, original = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    newer = deepcopy(original)
    if change == "account":
        newer["state"]["learning_account_epoch"] = "switched-away-and-back"
    elif change == "learning":
        newer["state"]["learning_erasure_epoch"] = "after-erasure"
    elif change == "reset":
        newer["state"]["learning_reset_epoch"] = "after-reset"
    else:
        newer["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "complete"}}
    raw_store(stores).write(newer, revision=1)
    with pytest.raises(StateConflict, match="stale"):
        store.update_learning_session(revision=2, account="default", operation_id=operation,
                                      changes={"topic": "old result"})
    with pytest.raises(StateConflict, match="stale"):
        store.save_adaptation(revision=2, account="default", operation_id=operation,
                              model=original["models"]["default"])
    assert raw_store(stores).read() == (newer, 2)
    fresh = store.begin_operation(revision=2, account="default", route="/fixture")
    _, revision = store.update_learning_session(revision=2, account="default", operation_id=fresh,
                                                changes={"topic": "new result"})
    assert revision == 3


def test_admission_fence_failure_rolls_back_quota_and_operation(transactions, postgres):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    postgres("""
CREATE FUNCTION public.test_reject_operation_fence() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_operation_fence BEFORE INSERT ON public.mammoth_learner_operation_fences
FOR EACH ROW EXECUTE FUNCTION public.test_reject_operation_fence();
""")
    try:
        with pytest.raises(StateUnavailable):
            store.begin_operation(revision=1, account="default", route="/fixture")
        snapshot = controls.snapshot()
        assert snapshot["admitted_requests"] == 0 and snapshot["operations"] == []
        assert store._store.read() == (original, 1)
    finally:
        postgres("DROP TRIGGER test_reject_operation_fence ON public.mammoth_learner_operation_fences; "
                 "DROP FUNCTION public.test_reject_operation_fence();")


def test_operation_fences_are_private_and_follow_operation_retention(transactions, postgres):
    store, _ = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    for role in ("anon", "authenticated"):
        result = postgres(
            f"SET ROLE {role}; SELECT * FROM public.mammoth_learner_operation_fences", check=False)
        assert result.returncode != 0 and "permission denied" in result.stderr
    namespace = store.namespace
    assert postgres(
        "SET ROLE service_role; SELECT count(*) FROM public.mammoth_learner_operation_fences "
        f"WHERE namespace='{namespace}' AND user_id='owner' AND operation_id='{operation}'"
    ) == "1"
    postgres(
        "SET ROLE service_role; DELETE FROM public.mammoth_learning_operations "
        f"WHERE namespace='{namespace}' AND user_id='owner' AND id='{operation}'"
    )
    assert postgres(
        "SET ROLE service_role; SELECT count(*) FROM public.mammoth_learner_operation_fences "
        f"WHERE namespace='{namespace}' AND user_id='owner' AND operation_id='{operation}'"
    ) == "0"


def test_learning_session_failed_write_rolls_back_without_cancelling_operation(transactions, postgres):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    postgres("""
CREATE FUNCTION public.test_reject_session_update() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_session_update BEFORE UPDATE ON public.mammoth_learner_bundles
FOR EACH ROW EXECUTE FUNCTION public.test_reject_session_update();
""")
    try:
        with pytest.raises(StateUnavailable):
            store.update_learning_session(revision=1, account="default", operation_id=operation,
                                          changes={"topic": "uncommitted"})
        assert store._store.read() == (original, 1)
        assert not controls.is_cancelled(operation)
    finally:
        postgres("DROP TRIGGER test_reject_session_update ON public.mammoth_learner_bundles; "
                 "DROP FUNCTION public.test_reject_session_update();")


@pytest.fixture
def switchable(transactions, stores):
    store, original = transactions
    bundle = deepcopy(original)
    bundle["state"]["accounts"] = {
        "default": {"profile": {"display_name": "First"}, "tier": "pro", "developer_access": True},
        "other": {"profile": {"display_name": "Second"}, "tier": "explorer", "developer_access": False},
    }
    bundle["state"]["account_sessions"]["default"]["extension"] = {"preserve": True}
    bundle["state"]["account_sessions"]["other"].update(
        topic="Other lesson", current_exercise={"prompt": "Other exercise"}, status="learning")
    raw_store(stores).write(bundle, revision=1)
    return store, bundle


def test_switch_account_fences_operations_and_preserves_sessions(switchable, stores):
    store, original = switchable
    draft, revision = save(store, original, revision=2)
    operation = store.begin_operation(revision=revision, account="default", route="/fixture")
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    revision = store.switch_account(revision=revision, account="default", target="other")
    switched, _ = raw_store(stores).read()
    assert revision == 4 and controls.is_cancelled(operation)
    assert switched["state"]["active_account_id"] == "other"
    assert switched["state"]["account_profile"] == {"display_name": "Second"}
    assert switched["state"]["topic"] == "Other lesson"
    assert "learner_model" not in switched["state"] and "learner_context" not in switched["state"]
    assert switched["state"]["account_sessions"]["default"]["extension"] == {"preserve": True}
    assert switched["models"] == original["models"]
    assert switched["drafts"]["default"]["values"]["lesson_response"] == "Private draft"
    epoch = switched["state"]["learning_account_epoch"]
    assert store.switch_account(revision=revision, account="other", target="other") == revision
    revision = store.switch_account(revision=revision, account="other", target="default")
    back, _ = raw_store(stores).read()
    assert revision == 5 and back["state"]["learning_account_epoch"] != epoch
    recovered, _ = store.read_workspace(account="default", revision=revision)
    assert recovered["values"]["lesson_response"] == "Private draft"
    assert recovered["exercise_key"] != draft["exercise_key"]
    with pytest.raises(StateConflict):
        store.update_learning_session(revision=revision, account="default", operation_id=operation,
                                      changes={"topic": "old result"})
    assert raw_store(stores).read() == (back, revision)


def test_switch_account_rejects_stale_unknown_or_corrupt_data(switchable, stores):
    store, original = switchable
    with pytest.raises(StateConflict):
        store.switch_account(revision=1, account="default", target="other")
    with pytest.raises(StateConflict):
        store.switch_account(revision=2, account="default", target="absent")
    with pytest.raises(ValueError):
        store.switch_account(revision=2, account="default", target="Bad/target")
    damaged = deepcopy(original)
    damaged["state"]["accounts"]["other"]["profile"] = "invalid"
    raw_store(stores).write(damaged, revision=2)
    with pytest.raises(StateUnavailable, match="profile"):
        store.switch_account(revision=3, account="default", target="other")
    assert raw_store(stores).read() == (damaged, 3)
    damaged["state"]["accounts"]["other"]["profile"] = {"display_name": "Second"}
    damaged["state"]["accounts"]["other"]["tier"] = []
    raw_store(stores).write(damaged, revision=3)
    with pytest.raises(StateUnavailable, match="profile"):
        store.switch_account(revision=4, account="default", target="other")
    assert raw_store(stores).read() == (damaged, 4)


def test_account_switch_rolls_back_operation_cancellation_on_failure(switchable, postgres):
    store, original = switchable
    operation = store.begin_operation(revision=2, account="default", route="/fixture")
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    postgres("""
CREATE FUNCTION public.test_reject_account_switch() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_account_switch BEFORE UPDATE ON public.mammoth_learner_bundles
FOR EACH ROW EXECUTE FUNCTION public.test_reject_account_switch();
""")
    try:
        with pytest.raises(StateUnavailable):
            store.switch_account(revision=2, account="default", target="other")
        assert store._store.read() == (original, 2)
        assert not controls.is_cancelled(operation)
    finally:
        postgres("DROP TRIGGER test_reject_account_switch ON public.mammoth_learner_bundles; "
                 "DROP FUNCTION public.test_reject_account_switch();")


def test_switch_and_session_write_serialize(switchable):
    store, _ = switchable
    operation = store.begin_operation(revision=2, account="default", route="/fixture")

    def run(kind):
        try:
            if kind == "switch":
                store.switch_account(revision=2, account="default", target="other")
            else:
                store.update_learning_session(revision=2, account="default", operation_id=operation,
                                              changes={"topic": "new"})
            return kind
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ("switch", "update")))
    assert results.count("conflict") == 1
    assert store._store.read()[1] == 3


def test_workspace_collections_are_scoped_revision_checked_and_preserve_other_data(switchable, stores):
    store, original = switchable
    fields, guard, revision = store.read_workspace_collections(account="default")
    assert fields == {
        "workspace_artifacts": [], "agent_run_history": [], "curriculum_library": [],
    } and revision == 2
    values = [{"id": "artifact", "body": "account-specific"}]
    revision = store.update_workspace_collection(
        revision=revision, account="default", guard=guard, field="workspace_artifacts",
        values=values, updated_at="2026-01-01",
    )
    saved, _ = raw_store(stores).read()
    assert saved["state"]["workspace_artifacts"] == values
    assert saved["state"]["account_sessions"]["default"]["workspace_artifacts"] == values
    assert saved["state"]["account_sessions"]["default"]["extension"] == {"preserve": True}
    assert saved["state"]["account_sessions"]["other"] == original["state"]["account_sessions"]["other"]
    assert saved["models"] == original["models"] and saved["drafts"] == original["drafts"]
    with pytest.raises(StateConflict):
        store.update_workspace_collection(
            revision=2, account="default", guard=guard, field="agent_run_history",
            values=[], updated_at="2026-01-01",
        )
    with pytest.raises(StateConflict):
        store.read_workspace_collections(account="other")
    assert raw_store(stores).read() == (saved, revision)


def test_curriculum_collection_is_bounded_and_revision_checked(switchable):
    store, _ = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    curriculum = {
        "curriculum_id": "course-one",
        "subject": "Python",
        "modules": [{"lessons": [{"lesson_id": "lesson-one"}]}],
    }
    record = {"curriculum": curriculum, "saved_at": "2026-01-01"}
    revision = store.update_workspace_collection(
        revision=revision, account="default", guard=guard, field="curriculum_library",
        values=[record], updated_at="2026-01-01",
    )
    fields, _, loaded_revision = store.read_workspace_collections(account="default")
    assert loaded_revision == revision and fields["curriculum_library"] == [record]
    for invalid in (
        [{"curriculum": curriculum}],
        [record, record],
        [{"curriculum": {}, "saved_at": "2026-01-01"}],
    ):
        with pytest.raises(ValueError, match="curriculum library"):
            store.update_workspace_collection(
                revision=revision, account="default", guard=guard, field="curriculum_library",
                values=invalid, updated_at="2026-01-01",
            )


def test_active_account_lookup_is_owner_scoped_and_never_bootstraps(switchable, stores):
    store, original = switchable
    assert store.read_active_account() == ("default", 2)
    other_owner = PostgresLearnerTransactions(store.dsn, store.namespace, "different-owner")
    with pytest.raises(StateConflict):
        other_owner.read_active_account()
    assert other_owner._store.read()[1] == 0
    changed = deepcopy(original)
    changed["state"]["accounts"].pop("default")
    raw_store(stores).write(changed, revision=2)
    with pytest.raises(StateUnavailable, match="missing"):
        store.read_active_account()
    assert raw_store(stores).read() == (changed, 3)


@pytest.mark.parametrize("change", ["switch", "create", "learning", "adaptation", "reset"])
def test_workspace_collection_stale_guard_never_allows_current_revision_replay(switchable, stores, change):
    store, _ = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    if change == "switch":
        revision = store.switch_account(revision=revision, account="default", target="other")
        revision = store.switch_account(revision=revision, account="other", target="default")
    elif change == "create":
        revision = store.create_account(
            revision=revision, account="default", target="new",
            profile={"display_name": "New", "email": "", "organization": ""},
            created_at="2026-01-01", activate=False,
        )
    elif change in ("learning", "adaptation"):
        _, revision = erase(store, change, revision=revision, account="default")
    else:
        revision = store.reset_learner(
            revision=revision, account="default", approval_guard=guard,
            session_reset=True, saved_at="2026-01-01",
        )
    before = raw_store(stores).read()
    with pytest.raises(StateConflict, match="changed"):
        store.update_workspace_collection(
            revision=revision, account="default", guard=guard, field="agent_run_history",
            values=[{"id": "stale"}], updated_at="2026-01-01",
        )
    assert raw_store(stores).read() == before


def test_workspace_collections_reject_unsupported_invalid_and_corrupt_data(switchable, stores):
    store, original = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    for field, values in (("topic", []), ("workspace_artifacts", [{}] * 121),
                          ("agent_run_history", ["bad"]), ("workspace_artifacts", [{"bad": float("nan")}])):
        with pytest.raises(ValueError):
            store.update_workspace_collection(
                revision=revision, account="default", guard=guard, field=field,
                values=values, updated_at="2026-01-01",
            )
    assert raw_store(stores).read() == (original, revision)
    damaged = deepcopy(original)
    damaged["state"]["workspace_artifacts"] = {"unsupported": True}
    raw_store(stores).write(damaged, revision=revision)
    with pytest.raises(StateUnavailable, match="collections"):
        store.read_workspace_collections(account="default")
    with pytest.raises(StateUnavailable, match="collections"):
        store.update_workspace_collection(
            revision=revision + 1, account="default", guard=guard,
            field="workspace_artifacts", values=[], updated_at="2026-01-01",
        )
    assert raw_store(stores).read() == (damaged, revision + 1)


def test_workspace_collection_guard_cannot_be_reused_across_owners(switchable, stores):
    store, original = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    other = PostgresLearnerTransactions(store.dsn, store.namespace, "different-owner")
    other._store.write(deepcopy(original), revision=0)
    with pytest.raises(StateConflict, match="changed"):
        other.update_workspace_collection(
            revision=1, account="default", guard=guard, field="workspace_artifacts",
            values=[{"private": "do not copy"}], updated_at="2026-01-01",
        )
    assert other._store.read() == (original, 1)
    assert raw_store(stores).read() == (original, revision)


def test_workspace_collection_read_normalization_preserves_existing_timestamps(switchable, stores):
    store, original = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    revision = store.update_workspace_collection(
        revision=revision, account="default", guard=guard, field="workspace_artifacts",
        values=[], updated_at=None,
    )
    saved, _ = raw_store(stores).read()
    assert saved["state"].get("updated_at") == original["state"].get("updated_at")
    assert (saved["state"]["account_sessions"]["default"].get("updated_at")
            == original["state"]["account_sessions"]["default"].get("updated_at"))
    assert revision == 3


def test_workspace_collection_write_failure_does_not_change_bundle(switchable, postgres):
    store, original = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    postgres("""
CREATE FUNCTION public.test_reject_workspace_collection() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_workspace_collection BEFORE UPDATE ON public.mammoth_learner_bundles
FOR EACH ROW EXECUTE FUNCTION public.test_reject_workspace_collection();
""")
    try:
        with pytest.raises(StateUnavailable):
            store.update_workspace_collection(
                revision=revision, account="default", guard=guard, field="workspace_artifacts",
                values=[{"id": "not committed"}], updated_at="2026-01-01",
            )
        assert store._store.read() == (original, revision)
    finally:
        postgres("DROP TRIGGER test_reject_workspace_collection ON public.mammoth_learner_bundles; "
                 "DROP FUNCTION public.test_reject_workspace_collection();")


def test_workspace_collection_simultaneous_updates_reject_lost_writes(switchable):
    store, _ = switchable
    _, guard, revision = store.read_workspace_collections(account="default")
    def write(field):
        try:
            store.update_workspace_collection(
                revision=revision, account="default", guard=guard, field=field,
                values=[{"id": field}], updated_at="2026-01-01",
            )
            return "saved"
        except StateConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ("workspace_artifacts", "agent_run_history"))) == ["conflict", "saved"]


@pytest.mark.parametrize("change", ["create", "delete"])
def test_inactive_account_changes_fence_prior_operations_and_approvals(switchable, stores, change):
    store, original = switchable
    operation = store.begin_operation(revision=2, account="default", route="/fixture")
    guard, _ = store.read_approval_guard(account="default")
    if change == "create":
        revision = store.create_account(
            revision=2, account="default", target="new",
            profile={"display_name": "New", "email": "", "organization": ""},
            created_at="2026-01-01T00:00:00+00:00", activate=False,
        )
    else:
        revision = store.delete_account(
            revision=2, account="default", target="other", deleted_at="2026-01-01T00:00:00+00:00",
        )
    changed, _ = raw_store(stores).read()
    assert changed["state"]["account_collections_epoch"] != original["state"].get("account_collections_epoch")
    assert changed["state"]["active_account_id"] == "default"
    with pytest.raises(StateConflict, match="operation"):
        store.update_learning_session(
            revision=revision, account="default", operation_id=operation, changes={"topic": "stale"},
        )
    with pytest.raises(StateConflict, match="approval"):
        store.update_onboarding(revision=revision, account="default", approval_guard=guard, onboarding={})
    assert raw_store(stores).read() == (changed, revision)


def test_switch_and_operation_admission_are_coordinated(switchable):
    store, _ = switchable
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)

    def begin():
        try:
            return store.begin_operation(revision=2, account="default", route="/fixture")
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        started = pool.submit(begin)
        switched = pool.submit(store.switch_account, revision=2, account="default", target="other")
        operation, revision = started.result(), switched.result()
    assert revision == 3
    if operation is not None:
        assert controls.is_cancelled(operation)
    with pytest.raises(StateConflict):
        store.begin_operation(revision=2, account="default", route="/fixture")


@pytest.mark.parametrize("activate", [True, False])
def test_create_account_is_atomic_and_respects_activation(switchable, stores, activate):
    store, original = switchable
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = store.begin_operation(revision=2, account="default", route="/fixture")
    profile = {"display_name": "Third", "email": "", "organization": ""}
    revision = store.create_account(revision=2, account="default", target="third",
                                    profile=profile, created_at="2026-01-01", activate=activate)
    saved, _ = raw_store(stores).read()
    assert revision == 3 and saved["state"]["accounts"]["third"]["profile"] == profile
    assert saved["state"]["account_sessions"]["third"]["status"] == "no_session"
    assert saved["state"]["active_account_id"] == ("third" if activate else "default")
    assert controls.is_cancelled(operation) is activate
    assert saved["models"] == original["models"] and saved["drafts"] == original["drafts"]
    with pytest.raises(StateConflict):
        store.create_account(revision=2, account="default", target="fourth",
                             profile=profile, created_at="now")
    if not activate:
        with pytest.raises(StateConflict):
            store.create_account(revision=3, account="default", target="third",
                                 profile=profile, created_at="now")


@pytest.mark.parametrize("target", ["default", "other"])
def test_delete_account_preserves_models_drafts_and_cancels_target(switchable, stores, target):
    store, original = switchable
    draft, revision = save(store, original, revision=2)
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    active = store.begin_operation(revision=revision, account="default", route="/fixture")
    other = controls.begin("/fixture", "other")
    before, _ = raw_store(stores).read()
    revision = store.delete_account(revision=revision, account="default", target=target, deleted_at="2026-01-01")
    saved, _ = raw_store(stores).read()
    assert revision == 4 and target not in saved["state"]["accounts"]
    assert target not in saved["state"]["account_sessions"]
    assert saved["models"] == before["models"] and saved["drafts"] == before["drafts"]
    assert controls.is_cancelled(active) is (target == "default")
    assert controls.is_cancelled(other) is (target == "other")
    assert saved["state"]["active_account_id"] == ("other" if target == "default" else "default")
    with pytest.raises(StateConflict):
        store.delete_account(revision=revision, account=saved["state"]["active_account_id"],
                             target=saved["state"]["active_account_id"], deleted_at="later")
    assert raw_store(stores).read() == (saved, revision)


def test_account_create_rejects_unassigned_session_and_invalid_values(switchable, stores):
    store, original = switchable
    profile = {"display_name": "Third", "email": "", "organization": ""}
    damaged = deepcopy(original)
    damaged["state"]["account_sessions"]["third"] = {"unknown": "must preserve"}
    raw_store(stores).write(damaged, revision=2)
    with pytest.raises(StateConflict, match="review"):
        store.create_account(revision=3, account="default", target="third", profile=profile, created_at="now")
    for bad in ({"display_name": "", "email": "", "organization": ""},
                {"display_name": "Third", "email": [], "organization": ""}, {}):
        with pytest.raises(ValueError):
            store.create_account(revision=3, account="default", target="third", profile=bad, created_at="now")
    assert raw_store(stores).read() == (damaged, 3)


def test_invalid_saved_account_identity_blocks_lifecycle_without_changes(switchable, stores):
    store, original = switchable
    damaged = deepcopy(original)
    damaged["state"]["accounts"]["Bad/identity"] = {"profile": {}}
    raw_store(stores).write(damaged, revision=2)
    for action in (
        lambda: store.switch_account(revision=3, account="default", target="other"),
        lambda: store.delete_account(revision=3, account="default", target="default", deleted_at="now"),
        lambda: store.create_account(
            revision=3, account="default", target="third",
            profile={"display_name": "Third", "email": "", "organization": ""}, created_at="now"),
    ):
        with pytest.raises(StateUnavailable, match="collections"):
            action()
    assert raw_store(stores).read() == (damaged, 3)


def test_delete_and_recreate_fences_old_work_without_erasing_retained_data(switchable, stores):
    store, original = switchable
    _, revision = save(store, original, revision=2)
    old_operation = store.begin_operation(revision=revision, account="default", route="/fixture")
    revision = store.delete_account(revision=revision, account="default", target="default", deleted_at="deleted")
    retained, _ = raw_store(stores).read()
    revision = store.create_account(
        revision=revision, account="other", target="default",
        profile={"display_name": "Recreated", "email": "", "organization": ""},
        created_at="recreated", activate=True)
    recreated, _ = raw_store(stores).read()
    assert recreated["drafts"] == retained["drafts"] and recreated["models"] == retained["models"]
    with pytest.raises(StateConflict):
        store.update_learning_session(revision=revision, account="default", operation_id=old_operation,
                                      changes={"topic": "old result"})
    assert raw_store(stores).read() == (recreated, revision)


def test_competing_account_creations_do_not_overwrite(switchable):
    store, _ = switchable
    profile = {"display_name": "Third", "email": "", "organization": ""}

    def create(_):
        try:
            return store.create_account(revision=2, account="default", target="third",
                                        profile=profile, created_at="now", activate=False)
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert sorted(results, key=lambda value: value or 0) == [None, 3]
    assert store._store.read()[1] == 3


def test_delete_and_new_operation_are_coordinated(switchable):
    store, _ = switchable
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)

    def begin():
        try:
            return store.begin_operation(revision=2, account="default", route="/fixture")
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        started = pool.submit(begin)
        deleted = pool.submit(store.delete_account, revision=2, account="default",
                              target="default", deleted_at="now")
        operation, revision = started.result(), deleted.result()
    assert revision == 3
    if operation is not None:
        assert controls.is_cancelled(operation)
    with pytest.raises(StateConflict):
        store.begin_operation(revision=2, account="default", route="/fixture")


@pytest.mark.parametrize("action", ["create", "delete"])
def test_account_lifecycle_rolls_back_cancellation_on_database_error(switchable, postgres, action):
    store, original = switchable
    operation = store.begin_operation(revision=2, account="default", route="/fixture")
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    postgres("""
CREATE FUNCTION public.test_reject_account_lifecycle() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_account_lifecycle BEFORE UPDATE ON public.mammoth_learner_bundles
FOR EACH ROW EXECUTE FUNCTION public.test_reject_account_lifecycle();
""")
    try:
        with pytest.raises(StateUnavailable):
            if action == "create":
                store.create_account(revision=2, account="default", target="third",
                                     profile={"display_name": "Third", "email": "", "organization": ""},
                                     created_at="now")
            else:
                store.delete_account(revision=2, account="default", target="default", deleted_at="now")
        assert store._store.read() == (original, 2) and not controls.is_cancelled(operation)
    finally:
        postgres("DROP TRIGGER test_reject_account_lifecycle ON public.mammoth_learner_bundles; "
                 "DROP FUNCTION public.test_reject_account_lifecycle();")


def test_workspace_read_and_clear_are_account_scoped_and_revision_checked(transactions, stores):
    store, original = transactions
    workspace, revision = store.read_workspace(account="default")
    assert revision == 1 and workspace == workspace_snapshot(original["state"])
    with pytest.raises(StateConflict):
        store.read_workspace(account="other")
    with pytest.raises(StateConflict):
        PostgresLearnerTransactions(store.dsn, store.namespace, "another-owner").read_workspace(account="default")
    saved, revision = save(store, original)
    with pytest.raises(StateConflict):
        store.read_workspace(account="default", revision=1)
    assert store.read_workspace(account="default", revision=2) == (saved, 2)
    kwargs = dict(revision=2, account="default", exercise_key=saved["exercise_key"],
                  draft_revision=saved["revision"], saved_at="2026-01-02T00:00:00+00:00")
    with pytest.raises(StateConflict):
        store.clear_draft(**{**kwargs, "draft_revision": 0})
    with pytest.raises(StateConflict):
        store.clear_draft(**{**kwargs, "exercise_key": "wrong"})
    assert raw_store(stores).read()[1] == 2
    cleared, revision = store.clear_draft(**kwargs)
    assert revision == 3 and cleared["revision"] == 2
    assert cleared["values"] == workspace_snapshot(original["state"])["values"]
    assert cleared["saved_at"] == "2026-01-02T00:00:00+00:00"
    with pytest.raises(StateConflict):
        store.clear_draft(**kwargs)
    assert store.read_workspace(account="default") == (cleared, 3)


def test_saving_draft_preserves_unknown_record_extensions(transactions, stores):
    store, original = transactions
    _, revision = save(store, original)
    bundle, _ = raw_store(stores).read()
    bundle["drafts"]["default"]["extension"] = {"retain": "future format"}
    revision = raw_store(stores).write(bundle, revision=revision)
    current, _ = store.read_workspace(account="default", revision=revision)
    saved, revision = store.save_draft(
        revision=revision, account="default", exercise_key=current["exercise_key"],
        draft_revision=current["revision"], values={**current["values"], "lesson_response": "Updated"},
        saved_at="later")
    assert saved["revision"] == 2 and saved["values"]["lesson_response"] == "Updated"
    assert raw_store(stores).read()[0]["drafts"]["default"]["extension"] == {"retain": "future format"}


def test_draft_survives_account_switch_back_but_old_request_is_fenced(transactions, stores):
    store, original = transactions
    old, _ = save(store, original)
    bundle, revision = raw_store(stores).read()
    bundle["state"]["active_account_id"] = "other"
    bundle["state"]["learning_account_epoch"] = "switch-away"
    revision = raw_store(stores).write(bundle, revision=revision)
    bundle["state"]["active_account_id"] = "default"
    bundle["state"]["learning_account_epoch"] = "switch-back"
    revision = raw_store(stores).write(bundle, revision=revision)
    restored, _ = store.read_workspace(account="default", revision=revision)
    assert restored["values"]["lesson_response"] == "Private draft"
    assert restored["exercise_key"] != old["exercise_key"]
    with pytest.raises(StateConflict):
        store.save_draft(revision=revision, account="default", exercise_key=old["exercise_key"],
                         draft_revision=old["revision"], values=old["values"], saved_at="later")
    saved, revision = store.save_draft(
        revision=revision, account="default", exercise_key=restored["exercise_key"],
        draft_revision=restored["revision"], values={**restored["values"], "lesson_response": "resumed"},
        saved_at="later")
    assert saved["values"]["lesson_response"] == "resumed"
    disk = raw_store(stores).read()[0]["drafts"]["default"]
    assert disk["exercise_key"] == workspace_snapshot(original["state"])["exercise_key"]


def test_draft_clear_rejects_corruption_and_preserves_other_accounts(transactions, stores):
    store, original = transactions
    saved, revision = save(store, original)
    bundle, _ = raw_store(stores).read()
    bundle["drafts"]["other"] = deepcopy(bundle["drafts"]["default"])
    raw_store(stores).write(bundle, revision=revision)
    cleared, revision = store.clear_draft(
        revision=3, account="default", exercise_key=saved["exercise_key"],
        draft_revision=1, saved_at="2026-01-02T00:00:00+00:00")
    updated, _ = raw_store(stores).read()
    assert revision == 4 and updated["drafts"]["other"] == bundle["drafts"]["other"]
    updated["drafts"]["default"] = {"values": "invalid"}
    raw_store(stores).write(updated, revision=revision)
    with pytest.raises(StateUnavailable, match="workspace"):
        store.read_workspace(account="default")
    with pytest.raises(StateUnavailable, match="workspace"):
        store.clear_draft(revision=5, account="default", exercise_key=cleared["exercise_key"],
                          draft_revision=cleared["revision"], saved_at="2026-01-02")
    assert raw_store(stores).read() == (updated, 5)


def test_concurrent_draft_save_and_clear_do_not_overwrite_each_other(transactions):
    store, original = transactions
    workspace, revision = store.read_workspace(account="default")

    def update(kind):
        try:
            if kind == "save":
                save(store, original, revision=revision)
            else:
                store.clear_draft(revision=revision, account="default", exercise_key=workspace["exercise_key"],
                                  draft_revision=workspace["revision"], saved_at="2026-01-02")
            return kind
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ("save", "clear")))
    assert results.count("conflict") == 1
    assert store.read_workspace(account="default")[1] == 2


def test_deletion_atomically_cancels_active_account_and_fences_old_writes(transactions, stores):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    active = controls.begin("/fixture", "default")
    other = controls.begin("/fixture", "other")
    receipt, revision = erase(store, "adaptation", revision=1, account="default")
    state = store._store.read()[0]
    assert revision == 2 and len(receipt) == 32
    assert state["state"]["learner_erasure"]["default"] == {"epoch": receipt, "status": "complete"}
    assert "default" not in state["models"] and state["models"]["other"] == original["models"]["other"]
    assert "learner_model" not in state["state"] and "learner_context" not in state["state"]
    assert state["state"]["account_sessions"]["default"] == {"topic": "preserve"}
    assert state["state"]["account_sessions"]["other"] == original["state"]["account_sessions"]["other"]
    assert controls.is_cancelled(active) is True and controls.is_cancelled(other) is False
    with pytest.raises(StateConflict):
        save(store, original)
    with pytest.raises(StateConflict):
        raw_store(stores).write(original, revision=1)
    assert store._store.read()[0] == state


def test_unknown_model_extensions_and_invalid_records_block_deletion(transactions, stores):
    store, original = transactions
    changed = deepcopy(original)
    changed["models"]["default"]["unknown_extension"] = {"must": "preserve"}
    raw_store(stores).write(changed, revision=1)
    with pytest.raises(StateConflict, match="extensions"):
        erase(store, "adaptation", revision=2, account="default")
    assert store._store.read() == (changed, 2)
    changed["state"]["learner_erasure"] = {"default": {"epoch": "invalid", "status": "pending"}}
    raw_store(stores).write(changed, revision=2)
    with pytest.raises(StateUnavailable, match="fences"):
        erase(store, "adaptation", revision=3, account="default")
    assert store._store.read() == (changed, 3)


@pytest.mark.parametrize("kind,phrase", [
    ("adaptation", "DELETE PRIVATE ADAPTATION"), ("learning", "DELETE SAVED LEARNING"),
])
def test_database_failure_rolls_back_cancellation_and_deletion(transactions, postgres, kind, phrase):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = controls.begin("/fixture", "default")
    preview = getattr(store, f"preview_{kind}_erasure")(account="default")
    postgres("""
CREATE FUNCTION public.test_reject_learner_update() RETURNS trigger LANGUAGE plpgsql
AS $$ BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_learner_update BEFORE UPDATE ON public.mammoth_learner_bundles
FOR EACH ROW EXECUTE FUNCTION public.test_reject_learner_update();
""")
    try:
        with pytest.raises(StateUnavailable):
            getattr(store, f"confirm_{kind}_erasure")(
                revision=1, account="default", confirmation=phrase, preview_token=preview["preview_token"])
        assert store._store.read() == (original, 1)
        assert controls.is_cancelled(operation) is False
    finally:
        postgres("DROP TRIGGER test_reject_learner_update ON public.mammoth_learner_bundles; "
                 "DROP FUNCTION public.test_reject_learner_update();")


def test_concurrent_draft_and_erasure_cannot_both_commit_same_revision(transactions):
    store, original = transactions

    def run(operation):
        try:
            if operation == "draft":
                save(store, original)
            else:
                erase(store, "adaptation", revision=1, account="default")
            return operation
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(run, ("draft", "erase")))
    assert result.count("conflict") == 1
    assert store._store.read()[1] == 2


def test_model_write_requires_live_matching_operation_and_preserves_extensions(transactions, stores):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    other_operation = controls.begin("/fixture", "other")
    unfenced_operation = controls.begin("/fixture", "default")
    model = deepcopy(original["models"]["default"])
    model["mastery"]["evidence"] = 0.9
    for rejected in ("missing", other_operation, unfenced_operation):
        with pytest.raises(StateConflict, match="operation"):
            store.save_adaptation(revision=1, account="default", operation_id=rejected, model=model)
    assert store.save_adaptation(revision=1, account="default", operation_id=operation, model=model) == 2
    controls.cancel(operation)
    with pytest.raises(StateConflict, match="operation"):
        store.save_adaptation(revision=2, account="default", operation_id=operation, model=model)
    assert store._store.read()[0]["models"]["default"] == model

    bundle, revision = store._store.read()
    bundle["models"]["default"]["extension"] = {"unknown": "keep"}
    revision = raw_store(stores).write(bundle, revision=revision)
    fresh_operation = store.begin_operation(revision=revision, account="default", route="/fixture")
    with pytest.raises(StateConflict, match="extensions"):
        store.save_adaptation(revision=revision, account="default", operation_id=fresh_operation, model=model)
    model["extension"] = {"unknown": "keep"}
    assert store.save_adaptation(revision=revision, account="default",
                                 operation_id=fresh_operation, model=model) == revision + 1


def test_onboarding_atomically_updates_model_and_caches_with_fenced_approval(transactions, stores, tmp_path):
    import json
    from mammoth_os.learner_model import set_onboarding_profile

    store, original = transactions
    original["models"]["default"]["extension"] = {"retain": True}
    original["state"]["account_sessions"]["default"]["extension"] = {"retain": True}
    revision = raw_store(stores).write(original, revision=1)
    guard, read_revision = store.read_approval_guard(account="default")
    assert read_revision == revision
    payload = {"experience_level": "advanced", "goals": ["Compare evidence"]}
    (tmp_path / "atlas_learner_model.json").write_text(json.dumps(original["models"]["default"]), encoding="utf-8")
    local = set_onboarding_profile(user_id="workspace:default", onboarding=payload, storage_path=str(tmp_path))
    revision = store.update_onboarding(revision=revision, account="default", approval_guard=guard, onboarding=payload)
    bundle, saved_revision = raw_store(stores).read()
    model = bundle["models"]["default"]
    assert revision == saved_revision == 3
    for field in ("mastery", "confidence", "streak", "attempts", "extension"):
        assert model[field] == local[field]
    for field in ("experience_level", "goals", "preferred_pacing", "learning_style"):
        assert model["onboarding"][field] == local["onboarding"][field]
    state, session = bundle["state"], bundle["state"]["account_sessions"]["default"]
    for field in ("learner_model", "learner_context", "learner_profile", "learner_storage"):
        assert state[field] == session[field]
    assert state["learner_model"] == model
    assert session["extension"] == {"retain": True}
    assert state["account_sessions"]["other"] == original["state"]["account_sessions"]["other"]
    assert bundle["models"]["other"] == original["models"]["other"]
    assert bundle["drafts"] == original["drafts"]


@pytest.mark.parametrize("kind", ["adaptation", "learning"])
def test_stale_onboarding_approval_cannot_restore_erased_data(transactions, stores, kind):
    store, _ = transactions
    guard, revision = store.read_approval_guard(account="default")
    _, revision = erase(store, kind, revision=revision, account="default")
    after = raw_store(stores).read()
    with pytest.raises(StateConflict, match="approval"):
        store.update_onboarding(revision=revision, account="default", approval_guard=guard,
                                onboarding={"goals": ["stale"]})
    assert raw_store(stores).read() == after


def test_onboarding_approval_rejects_switch_away_back_and_wrong_owner(switchable, stores):
    store, _ = switchable
    guard, revision = store.read_approval_guard(account="default")
    other = PostgresLearnerTransactions(store.dsn, store.namespace, "another-owner")
    other_guard = {**guard, "owner": other.user_id}
    with pytest.raises(StateConflict, match="approval"):
        store.update_onboarding(revision=revision, account="default", approval_guard=other_guard, onboarding={})
    revision = store.switch_account(revision=revision, account="default", target="other")
    revision = store.switch_account(revision=revision, account="other", target="default")
    after = raw_store(stores).read()
    with pytest.raises(StateConflict, match="approval"):
        store.update_onboarding(revision=revision, account="default", approval_guard=guard,
                                onboarding={"goals": ["old approval"]})
    assert raw_store(stores).read() == after


def test_onboarding_and_adaptation_erasure_have_one_atomic_winner(transactions, stores):
    store, _ = transactions
    guard, revision = store.read_approval_guard(account="default")
    preview = store.preview_adaptation_erasure(account="default")

    def run(action):
        try:
            if action == "onboarding":
                store.update_onboarding(revision=revision, account="default", approval_guard=guard,
                                        onboarding={"goals": ["current"]})
            else:
                store.confirm_adaptation_erasure(revision=revision, account="default",
                                                 confirmation="DELETE PRIVATE ADAPTATION",
                                                 preview_token=preview["preview_token"])
            return action
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ("onboarding", "erase")))
    assert results.count("conflict") == 1
    bundle, current_revision = raw_store(stores).read()
    assert current_revision == revision + 1
    if "erase" in results:
        assert "default" not in bundle["models"]
        assert "learner_model" not in bundle["state"]
        assert "learner_model" not in bundle["state"]["account_sessions"]["default"]
    else:
        assert bundle["models"]["default"]["onboarding"]["goals"] == ["current"]
        assert bundle["state"]["learner_model"] == bundle["models"]["default"]


def test_onboarding_invalid_input_database_failure_and_pending_erasure_fail_closed(transactions, stores):
    store, original = transactions
    guard, revision = store.read_approval_guard(account="default")
    for invalid in ({"experience_level": "unsupported"}, {"goals": ["\x00"]}, {"extension": float("nan")}):
        with pytest.raises((ValueError, StateUnavailable)):
            store.update_onboarding(revision=revision, account="default", approval_guard=guard, onboarding=invalid)
        assert raw_store(stores).read() == (original, revision)
    pending = deepcopy(original)
    pending["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    revision = raw_store(stores).write(pending, revision=revision)
    with pytest.raises(StateConflict, match="pending"):
        store.read_approval_guard(account="default")
    with pytest.raises(StateConflict, match="pending"):
        store.update_onboarding(revision=revision, account="default", approval_guard=guard, onboarding={})
    assert raw_store(stores).read() == (pending, revision)


@pytest.mark.parametrize("session_reset", [False, True])
def test_reset_atomically_updates_model_state_draft_and_cancels_stale_work(transactions, stores, session_reset):
    store, original = transactions
    saved_draft, revision = save(store, original)
    operation = store.begin_operation(revision=revision, account="default", route="/fixture")
    guard, _ = store.read_approval_guard(account="default")
    before, _ = raw_store(stores).read()
    revision = store.reset_learner(revision=revision, account="default", approval_guard=guard,
                                   session_reset=session_reset, saved_at="2026-01-01T01:00:00+00:00")
    bundle, current_revision = raw_store(stores).read()
    state, model = bundle["state"], bundle["models"]["default"]
    session = state["account_sessions"]["default"]
    assert revision == current_revision == 3
    assert model["mastery"] == model["confidence"] == {} and model["attempts"] == model["streak"] == 0
    assert state["learner_model"] == session["learner_model"] == model
    assert state["learner_profile"] == session["learner_profile"]
    assert state["workspace_epoch"] == session["workspace_epoch"] != before["state"]["workspace_epoch"]
    assert state["learning_reset_epoch"]
    draft, _ = store.read_workspace(account="default", revision=revision)
    assert draft["revision"] == saved_draft["revision"] + 1
    assert draft["values"]["lesson_response"] != "Private draft"
    assert draft["exercise_key"] != saved_draft["exercise_key"]
    assert PostgresLearningControls(store.dsn, store.namespace, store.user_id).is_cancelled(operation)
    assert bundle["models"]["other"] == before["models"]["other"]
    assert state["account_sessions"]["other"] == before["state"]["account_sessions"]["other"]
    if session_reset:
        assert state["status"] == session["status"] == "reset"
        assert "lesson_telemetry" not in state
        assert "lesson_telemetry" not in session
    with pytest.raises(StateConflict, match="approval"):
        store.update_onboarding(revision=revision, account="default", approval_guard=guard, onboarding={})
    with pytest.raises(StateConflict, match="operation"):
        store.record_learning_result(revision=revision, account="default", operation_id=operation,
                                     result={"passed": True}, changes={"topic": "Stale"})
    assert raw_store(stores).read() == (bundle, revision)
    new_operation = store.begin_operation(revision=revision, account="default", route="/new")
    assert store.record_learning_result(revision=revision, account="default", operation_id=new_operation,
                                        result={"passed": True}, changes={"topic": "Fresh"}) == revision + 1


def test_reset_rejects_corrupt_draft_and_stale_or_invalid_guard(transactions, stores):
    store, original = transactions
    guard, revision = store.read_approval_guard(account="default")
    with pytest.raises(StateConflict, match="approval"):
        store.reset_learner(revision=revision, account="default", approval_guard={},
                            session_reset=True, saved_at="2026-01-01")
    damaged = deepcopy(original)
    damaged["drafts"]["default"] = {"revision": True}
    revision = raw_store(stores).write(damaged, revision=revision)
    with pytest.raises(StateUnavailable, match="workspace"):
        store.reset_learner(revision=revision, account="default", approval_guard=guard,
                            session_reset=True, saved_at="2026-01-01")
    assert raw_store(stores).read() == (damaged, revision)


def test_reset_rolls_back_model_draft_and_cancellation_on_database_error(transactions, stores, postgres):
    store, original = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    guard, revision = store.read_approval_guard(account="default")
    postgres("""
CREATE FUNCTION public.test_reject_learner_reset() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'fixture failure'; END $$;
CREATE TRIGGER test_reject_learner_reset BEFORE UPDATE ON public.mammoth_learner_bundles
FOR EACH ROW EXECUTE FUNCTION public.test_reject_learner_reset();
""")
    try:
        with pytest.raises(StateUnavailable):
            store.reset_learner(revision=revision, account="default", approval_guard=guard,
                                session_reset=True, saved_at="2026-01-01T01:00:00+00:00")
        assert raw_store(stores).read() == (original, revision)
        assert not PostgresLearningControls(store.dsn, store.namespace, store.user_id).is_cancelled(operation)
    finally:
        postgres("DROP TRIGGER test_reject_learner_reset ON public.mammoth_learner_bundles; "
                 "DROP FUNCTION public.test_reject_learner_reset();")


def test_learning_result_commits_model_session_and_caches_together(transactions, stores, tmp_path):
    from mammoth_os.learner_model import learner_storage_scope, update_learner_model
    import json

    store, original = transactions
    original["models"]["default"]["extension"] = {"retain": True}
    original["state"]["account_sessions"]["default"]["extension"] = {"retain": True}
    revision = raw_store(stores).write(original, revision=1)
    operation = store.begin_operation(revision=revision, account="default", route="/fixture")
    result = {"passed": True, "feedback": "Evidence"}
    lesson = {"title": "Evidence"}
    (tmp_path / "atlas_learner_model.json").write_text(
        json.dumps(original["models"]["default"]), encoding="utf-8")
    local = update_learner_model("workspace:default", lesson=lesson, result=result,
                                 topic="Evidence", storage_path=str(tmp_path))
    revision = store.record_learning_result(
        revision=revision, account="default", operation_id=operation, result=result,
        lesson=lesson, topic="Evidence", changes={"topic": "Evidence", "last_submission": result})
    bundle, saved_revision = raw_store(stores).read()
    model = bundle["models"]["default"]
    assert revision == saved_revision == 3
    for field in ("attempts", "streak", "mastery", "confidence", "error_patterns", "extension"):
        assert model[field] == local[field]
    assert model["extension"] == {"retain": True}
    state, session = bundle["state"], bundle["state"]["account_sessions"]["default"]
    for field in ("last_submission", "topic", "learner_model", "learner_context",
                  "learner_profile", "learner_storage"):
        assert state[field] == session[field]
    assert state["learner_model"] == model
    assert state["learner_profile"]["attempts"] == model["attempts"]
    assert state["learner_storage"] == learner_storage_scope(store.user_id, "workspace:default")
    assert session["extension"] == {"retain": True}
    assert state["account_sessions"]["other"] == original["state"]["account_sessions"]["other"]
    assert bundle["models"]["other"] == original["models"]["other"]
    assert bundle["drafts"] == original["drafts"]


def test_learning_result_failure_or_stale_operation_never_partially_commits(transactions, stores):
    store, original = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    for changes in ({"learner_model": {}}, {"topic": float("nan")}):
        with pytest.raises(ValueError):
            store.record_learning_result(revision=1, account="default", operation_id=operation,
                                         result={"passed": True}, changes=changes)
        assert raw_store(stores).read() == (original, 1)
    with pytest.raises(StateUnavailable):
        store.record_learning_result(revision=1, account="default", operation_id=operation,
                                     result={"passed": True}, changes={"topic": "\x00"})
    assert raw_store(stores).read() == (original, 1)
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    controls.cancel(operation)
    with pytest.raises(StateConflict, match="operation"):
        store.record_learning_result(revision=1, account="default", operation_id=operation,
                                     result={"passed": True}, changes={"topic": "Too late"})
    assert raw_store(stores).read() == (original, 1)


@pytest.mark.parametrize("kind", ["adaptation", "learning"])
def test_learning_result_cannot_recreate_erased_data_with_new_revision(transactions, stores, kind):
    store, _ = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    _, revision = erase(store, kind, revision=1, account="default")
    after = raw_store(stores).read()
    with pytest.raises(StateConflict, match="operation"):
        store.record_learning_result(revision=revision, account="default", operation_id=operation,
                                     result={"passed": True}, changes={"topic": "Stale result"})
    assert raw_store(stores).read() == after


def test_learning_result_rejects_unfenced_admission_and_switch_away_back(switchable, stores):
    store, original = switchable
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    unfenced = controls.begin("/fixture", "default")
    operation = store.begin_operation(revision=2, account="default", route="/fixture")
    with pytest.raises(StateConflict, match="operation"):
        store.record_learning_result(revision=2, account="default", operation_id=unfenced,
                                     result={"passed": True}, changes={"topic": "Unfenced"})
    assert raw_store(stores).read() == (original, 2)
    revision = store.switch_account(revision=2, account="default", target="other")
    revision = store.switch_account(revision=revision, account="other", target="default")
    after = raw_store(stores).read()
    with pytest.raises(StateConflict, match="operation"):
        store.record_learning_result(revision=revision, account="default", operation_id=operation,
                                     result={"passed": True}, changes={"topic": "Stale"})
    assert raw_store(stores).read() == after


def test_learning_result_and_erasure_have_one_atomic_winner(transactions, stores):
    store, _ = transactions
    operation = store.begin_operation(revision=1, account="default", route="/fixture")

    def run(action):
        try:
            if action == "result":
                store.record_learning_result(
                    revision=1, account="default", operation_id=operation,
                    result={"passed": True}, changes={"topic": "Completed"})
            else:
                erase(store, "adaptation", revision=1, account="default")
            return action
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ("result", "erase")))
    assert results.count("conflict") == 1
    bundle, revision = raw_store(stores).read()
    assert revision == 2
    if "erase" in results:
        assert "default" not in bundle["models"]
        assert "learner_model" not in bundle["state"]
        assert "learner_model" not in bundle["state"]["account_sessions"]["default"]
    else:
        assert bundle["state"]["topic"] == "Completed"
        assert bundle["state"]["learner_model"] == bundle["models"]["default"]
        assert bundle["state"]["account_sessions"]["default"]["learner_model"] == bundle["models"]["default"]


def test_pending_erasure_and_stale_model_work_fail_without_changes(transactions, stores):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    pending = deepcopy(original)
    pending["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    raw_store(stores).write(pending, revision=1)
    with pytest.raises(StateConflict, match="pending"):
        store.save_adaptation(revision=2, account="default", operation_id=operation,
                              model=original["models"]["default"])
    epoch, revision = erase(store, "adaptation", revision=2, account="default")
    with pytest.raises(StateConflict):
        store.save_adaptation(revision=2, account="default", operation_id=operation,
                              model=original["models"]["default"])
    assert store._store.read()[0]["state"]["learner_erasure"]["default"] == {"epoch": epoch, "status": "complete"}
    assert store._store.read()[1] == revision and controls.is_cancelled(operation)


def test_concurrent_model_update_and_erasure_are_revision_serialized(transactions):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = store.begin_operation(revision=1, account="default", route="/fixture")
    model = deepcopy(original["models"]["default"])
    model["mastery"]["evidence"] = 0.9

    def run(action):
        try:
            if action == "model":
                store.save_adaptation(revision=1, account="default", operation_id=operation, model=model)
            else:
                erase(store, "adaptation", revision=1, account="default")
            return action
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ("model", "erase")))
    assert results.count("conflict") == 1
    current, revision = store._store.read()
    assert revision == 2
    if "erase" in results:
        assert "default" not in current["models"] and controls.is_cancelled(operation)
    else:
        assert current["models"]["default"] == model and not controls.is_cancelled(operation)


def test_corrupt_saved_draft_or_exercise_is_not_overwritten(transactions, stores):
    store, original = transactions
    bad = deepcopy(original)
    bad["drafts"]["default"] = {"revision": True, "values": {}}
    raw_store(stores).write(bad, revision=1)
    with pytest.raises(StateUnavailable, match="workspace"):
        save(store, original, revision=2)
    assert store._store.read() == (bad, 2)
    bad["drafts"] = {}
    bad["state"]["current_exercise"] = "invalid"
    raw_store(stores).write(bad, revision=2)
    with pytest.raises(StateUnavailable, match="exercise"):
        save(store, original, revision=3)
    assert store._store.read() == (bad, 3)


def test_learning_erasure_atomically_deletes_scoped_history_and_draft(transactions, stores):
    store, original = transactions
    bundle = deepcopy(original)
    state = bundle["state"]
    state["chat_history"] = [{"message": "erase"}]
    state["account_sessions"]["default"]["chat_history"] = [{"message": "erase"}]
    state["account_sessions"]["other"]["chat_history"] = [{"message": "preserve"}]
    state["mammoth_chat_history"] = [{"message": "outside scope"}]
    snapshot = workspace_snapshot(state)
    bundle["drafts"] = {
        "default": {"exercise_key": snapshot["exercise_key"], "revision": 1,
                    "values": snapshot["values"], "saved_at": "fixture"},
        "other": {"private": "unchanged"},
    }
    raw_store(stores).write(bundle, revision=1)
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = controls.begin("/fixture", "default")
    other = controls.begin("/fixture", "other")
    epoch, revision = erase(store, "learning", revision=2, account="default")
    saved, _ = store._store.read()
    assert revision == 3 and saved["state"]["learning_erasure_epoch"] == epoch
    assert "chat_history" not in saved["state"] and "current_exercise" not in saved["state"]
    assert "chat_history" not in saved["state"]["account_sessions"]["default"]
    assert saved["state"]["account_sessions"]["default"]["status"] == "no_session"
    assert saved["state"]["account_sessions"]["other"] == bundle["state"]["account_sessions"]["other"]
    assert saved["state"]["mammoth_chat_history"] == [{"message": "outside scope"}]
    assert "default" not in saved["drafts"] and saved["drafts"]["other"] == bundle["drafts"]["other"]
    assert saved["models"] == bundle["models"]
    assert controls.is_cancelled(operation) and not controls.is_cancelled(other)
    with pytest.raises(StateConflict):
        save(store, bundle, revision=2, draft_revision=1)
    assert store._store.read() == (saved, 3)


def test_operation_admission_and_erasure_serialize_on_the_same_owner(transactions):
    store, _ = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)

    def begin():
        try:
            return store.begin_operation(revision=1, account="default", route="/fixture")
        except StateConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        start = pool.submit(begin)
        deletion = pool.submit(erase, store, "learning", revision=1, account="default")
        operation = start.result()
        _, revision = deletion.result()
    assert revision == 2
    if operation is not None:
        assert controls.is_cancelled(operation)
    with pytest.raises(StateConflict):
        store.begin_operation(revision=1, account="default", route="/fixture")


def test_coordinated_admission_honors_limit_and_pending_deletion(transactions, stores):
    store, original = transactions
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    controls.set_limit(0)
    with pytest.raises(LearningLimitReached):
        store.begin_operation(revision=1, account="default", route="/fixture")
    assert controls.snapshot()["operations"] == []
    assert store._store.read() == (original, 1)
    pending = deepcopy(original)
    pending["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    raw_store(stores).write(pending, revision=1)
    with pytest.raises(StateConflict, match="pending"):
        store.begin_operation(revision=2, account="default", route="/fixture")
    assert controls.snapshot()["operations"] == []


def test_guarded_model_reads_and_deletion_preview_never_expose_pending_content(transactions, stores):
    store, original = transactions
    model, revision = store.read_adaptation(account="default")
    assert model == original["models"]["default"] and revision == 1
    with pytest.raises(StateConflict):
        store.read_adaptation(account="other")
    with pytest.raises(StateConflict):
        PostgresLearnerTransactions(store.dsn, store.namespace, "another-owner").read_adaptation(account="default")

    pending = deepcopy(original)
    pending["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    pending["models"]["default"]["extension"] = {"private": "do not reveal"}
    raw_store(stores).write(pending, revision=1)
    with pytest.raises(StateUnavailable, match="pending"):
        store.read_adaptation(account="default")
    preview = store.preview_adaptation_erasure(account="default")
    token = preview.pop("preview_token")
    assert len(token) == 64
    assert preview == {
        "contract": "mammoth.learner-erasure.v1",
        "account_id": "default", "revision": 2, "model_status": "saved",
        "scope": "active_account_private_model_and_adaptation_caches",
        "pending_deletion": True, "deletion_available": False,
        "cached_fields": ["learner_context", "learner_model"],
        "deletion_blockers": ["unknown_model_extensions_require_review"],
        "erases": ["private_model_onboarding_mastery_confidence_errors_outcomes_and_memory_graph",
                   "active_account_adaptation_caches"],
        "excludes": list(LEARNER_ERASURE_EXCLUDES),
        "cancels_tracked_account_requests": True, "provider_work_may_continue": True,
        "fresh_activity_can_create_new_adaptation": True,
    }
    assert "do not reveal" not in str(preview)


def test_preview_revision_fences_a_change_before_confirmed_deletion(transactions, stores):
    store, original = transactions
    preview = store.preview_adaptation_erasure(account="default")
    assert preview["revision"] == 1 and preview["deletion_available"]
    newer = deepcopy(original)
    newer["models"]["default"]["mastery"]["evidence"] = 0.3
    raw_store(stores).write(newer, revision=1)
    with pytest.raises(StateConflict):
        store.read_adaptation(account="default", revision=preview["revision"])
    with pytest.raises(StateConflict):
        store.confirm_adaptation_erasure(revision=preview["revision"], account="default",
                                         confirmation="DELETE PRIVATE ADAPTATION",
                                         preview_token=preview["preview_token"])
    assert raw_store(stores).read() == (newer, 2)


def test_guarded_model_read_filters_extensions_and_rejects_corruption(transactions, stores):
    store, original = transactions
    data = deepcopy(original)
    data["models"]["default"]["extension"] = {"private": "not exported"}
    raw_store(stores).write(data, revision=1)
    model, revision = store.read_adaptation(account="default")
    assert "extension" not in model and revision == 2
    data["models"]["default"]["user_id"] = "workspace:other"
    raw_store(stores).write(data, revision=2)
    with pytest.raises(StateUnavailable, match="invalid"):
        store.read_adaptation(account="default")
    with pytest.raises(StateUnavailable, match="invalid"):
        store.preview_adaptation_erasure(account="default")


def test_preview_rejects_invalid_account_sessions(transactions, stores):
    store, original = transactions
    data = deepcopy(original)
    data["state"]["account_sessions"] = {"default": "invalid"}
    raw_store(stores).write(data, revision=1)
    with pytest.raises(StateUnavailable, match="sessions"):
        store.preview_adaptation_erasure(account="default")


@pytest.mark.parametrize(
    "kind,phrase",
    [("adaptation", "DELETE PRIVATE ADAPTATION"), ("learning", "DELETE SAVED LEARNING")],
)
def test_confirmed_erasure_requires_scoped_current_preview(transactions, stores, kind, phrase):
    store, original = transactions
    preview = getattr(store, f"preview_{kind}_erasure")(account="default")
    other_kind = "learning" if kind == "adaptation" else "adaptation"
    other_preview = getattr(store, f"preview_{other_kind}_erasure")(account="default")
    confirm = getattr(store, f"confirm_{kind}_erasure")
    arguments = dict(revision=preview["revision"], account="default",
                     confirmation=phrase, preview_token=preview["preview_token"])
    controls = PostgresLearningControls(store.dsn, store.namespace, store.user_id)
    operation = controls.begin("/fixture", "default")
    for bad in ("", "DELETE", "DELETE PRIVATE ADAPTATION "):
        with pytest.raises(ValueError):
            confirm(**{**arguments, "confirmation": bad})
    for bad in ("", "é" * 64, None):
        with pytest.raises(ValueError):
            confirm(**{**arguments, "preview_token": bad})
    with pytest.raises(StateConflict):
        confirm(**{**arguments, "preview_token": other_preview["preview_token"]})
    assert raw_store(stores).read() == (original, 1)
    assert not controls.is_cancelled(operation)
    receipt, revision = confirm(**arguments)
    assert len(receipt) == 32 and revision == 2
    assert controls.is_cancelled(operation)
    with pytest.raises(StateConflict):
        confirm(**arguments)
    assert raw_store(stores).read()[1] == 2


def test_confirmation_token_is_bound_to_owner_and_full_snapshot(transactions, stores):
    store, original = transactions
    preview = store.preview_learning_erasure(account="default")
    other = PostgresLearnerTransactions(store.dsn, store.namespace, "another-owner")
    PostgresLearnerBundle(store.dsn, store.namespace, "another-owner").write(original, revision=0)
    with pytest.raises(StateConflict):
        other.confirm_learning_erasure(
            revision=1, account="default", confirmation="DELETE SAVED LEARNING",
            preview_token=preview["preview_token"])
    changed = deepcopy(original)
    changed["state"]["topic"] = "Changed saved learning"
    raw_store(stores).write(changed, revision=1)
    with pytest.raises(StateConflict):
        store.confirm_learning_erasure(
            revision=2, account="default", confirmation="DELETE SAVED LEARNING",
            preview_token=preview["preview_token"])
    assert raw_store(stores).read() == (changed, 2)


def test_confirmed_adaptation_erase_honors_unknown_extension_and_pending_retry(transactions, stores):
    store, original = transactions
    changed = deepcopy(original)
    changed["state"]["learner_erasure"] = {"default": {"epoch": "a" * 32, "status": "pending"}}
    changed["models"]["default"]["extension"] = {"private": "do not reveal"}
    raw_store(stores).write(changed, revision=1)
    preview = store.preview_adaptation_erasure(account="default")
    assert preview["pending_deletion"] and not preview["deletion_available"]
    with pytest.raises(StateConflict, match="extensions"):
        store.confirm_adaptation_erasure(
            revision=2, account="default", confirmation="DELETE PRIVATE ADAPTATION",
            preview_token=preview["preview_token"])
    assert raw_store(stores).read() == (changed, 2)
    del changed["models"]["default"]["extension"]
    raw_store(stores).write(changed, revision=2)
    preview = store.preview_adaptation_erasure(account="default")
    assert preview["pending_deletion"] and preview["deletion_available"]
    epoch, revision = store.confirm_adaptation_erasure(
        revision=3, account="default", confirmation="DELETE PRIVATE ADAPTATION",
        preview_token=preview["preview_token"])
    saved, _ = raw_store(stores).read()
    assert revision == 4 and "default" not in saved["models"]
    assert saved["state"]["learner_erasure"]["default"] == {"epoch": epoch, "status": "complete"}


def test_corrupt_draft_blocks_learning_preview_and_deletion(transactions, stores):
    store, original = transactions
    damaged = deepcopy(original)
    damaged["drafts"]["default"] = {"values": "invalid"}
    raw_store(stores).write(damaged, revision=1)
    with pytest.raises(StateUnavailable, match="workspace"):
        store.preview_learning_erasure(account="default")
    with pytest.raises(StateUnavailable, match="workspace"):
        erase(store, "learning", revision=2, account="default")
    assert raw_store(stores).read() == (damaged, 2)


@pytest.mark.parametrize("kind,phrase", [
    ("adaptation", "DELETE PRIVATE ADAPTATION"), ("learning", "DELETE SAVED LEARNING"),
])
def test_two_workers_cannot_confirm_the_same_preview_twice(transactions, kind, phrase):
    store, _ = transactions
    preview = getattr(store, f"preview_{kind}_erasure")(account="default")

    def confirm():
        try:
            getattr(store, f"confirm_{kind}_erasure")(
                revision=preview["revision"], account="default", confirmation=phrase,
                preview_token=preview["preview_token"])
            return "deleted"
        except StateConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: confirm(), range(2)))
    assert sorted(results) == ["conflict", "deleted"]
    assert store._store.read()[1] == 2
