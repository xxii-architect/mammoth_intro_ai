"""Unwired learner transaction experiments; not a runtime storage backend."""

import hashlib
import hmac
import json
import re
import uuid
from copy import deepcopy

from .learner_model import (
    DEFAULT_LEARNER_MODEL, LearnerStorageError, _apply_learning_result, _apply_onboarding_profile,
    _ensure_model_shape, _reset_model_progress,
    _now_iso, build_learner_context, learner_storage_scope, validate_saved_learner_model,
)
from .learning_workspace import (
    ACCOUNT_SESSION_FIELDS, ERASABLE_LEARNING_FIELDS, LEARNER_CACHE_FIELDS,
    LEARNER_ERASURE_EXCLUDES, LEARNING_ERASURE_EXCLUDES,
    WorkspaceStorageError, validate_learner_erasure_records, validate_workspace_record, validate_workspace_values,
    workspace_content_key, workspace_snapshot,
)
from .postgres_learner_bundle import PostgresLearnerBundle, _validate_bundle
from .postgres_learning_controls import PostgresLearningControls
from .shared_state import StateConflict, StateUnavailable

_CONFIRMATIONS = {
    "adaptation": "DELETE PRIVATE ADAPTATION",
    "learning": "DELETE SAVED LEARNING",
}
_LEARNING_SESSION_FIELDS = frozenset(ERASABLE_LEARNING_FIELDS) - {"learner_profile"} | {
    "lesson_telemetry", "status",
}
_WORKSPACE_COLLECTION_LIMITS = {
    "workspace_artifacts": 120, "agent_run_history": 160, "curriculum_library": 20,
}
_LEARNER_APPROVAL_OPERATIONS = {
    "atlas_onboard_update", "atlas_learner_reset", "atlas_session_reset",
}
_LEARNER_APPROVAL_AUDIT_LIMIT = 400


def _active_account(state):
    value = state.get("active_account_id") or state.get("current_account_id") or "default"
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) is None:
        raise StateUnavailable("Saved learner account identity is invalid; no change was confirmed.")
    return value


def _erasure_records(state):
    try:
        return validate_learner_erasure_records(state)
    except WorkspaceStorageError as exc:
        raise StateUnavailable("Saved learner erasure fences are invalid; no change was confirmed.") from exc


def _operation_fence(state, account):
    return {
        "account_epoch": state.get("learning_account_epoch"),
        "account_collections_epoch": state.get("account_collections_epoch"),
        "learning_erasure_epoch": state.get("learning_erasure_epoch"),
        "adaptation_erasure": _erasure_records(state).get(account),
        "reset_epoch": state.get("learning_reset_epoch"),
    }


class PostgresLearnerTransactions:
    """Revision-bound learner operations without a raw whole-bundle write method."""

    def __init__(self, dsn, namespace, user_id):
        self._store = PostgresLearnerBundle(dsn, namespace, user_id)
        self.dsn, self.namespace, self.user_id = self._store.dsn, self._store.namespace, self._store.user_id

    def _transaction(self):
        return self._store._transaction()

    def _locked_owner_snapshot(self, connection, revision=None):
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ValueError("A positive learner bundle revision is required.")
        row = connection.execute(
            "SELECT state,drafts,models,revision FROM public.mammoth_learner_bundles "
            "WHERE namespace=%s AND user_id=%s FOR UPDATE",
            (self.namespace, self.user_id),
        ).fetchone()
        if row is None or (revision is not None and row[3] != revision):
            raise StateConflict("Saved learner data changed; reload without replaying work.")
        bundle = {"state": row[0], "drafts": row[1], "models": row[2]}
        try:
            _validate_bundle(bundle)
        except ValueError as exc:
            raise StateUnavailable("Saved learner data is invalid; no change was confirmed.") from exc
        _erasure_records(bundle["state"])
        return bundle, row[3]

    def _locked_snapshot(self, connection, account, revision=None):
        bundle, revision = self._locked_owner_snapshot(connection, revision)
        if not isinstance(account, str) or _active_account(bundle["state"]) != account:
            raise StateConflict("The active learner account changed; reload before retrying.")
        return bundle, revision

    def read_active_account(self):
        """Return the active account and revision, never the owner's raw bundle."""
        with self._transaction() as connection:
            bundle, revision = self._locked_owner_snapshot(connection)
            account = _active_account(bundle["state"])
            self._account_collections(bundle["state"], account)
            return account, revision

    def _locked_bundle(self, connection, revision, account):
        if type(revision) is not int or revision < 1:
            raise ValueError("A positive learner bundle revision is required.")
        return self._locked_snapshot(connection, account, revision)[0]

    def read_adaptation(self, *, account, revision=None):
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account, revision)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateUnavailable("Private adaptation deletion is pending; adaptation cannot be read.")
            model = bundle["models"].get(account)
            if model is not None:
                try:
                    validate_saved_learner_model(model, f"workspace:{account}")
                except LearnerStorageError as exc:
                    raise StateUnavailable("Saved private adaptation is invalid; no data was returned.") from exc
                model = {key: model[key] for key in DEFAULT_LEARNER_MODEL if key in model}
        return model, revision

    def _preview_token(self, kind, account, revision, bundle):
        identity = [kind, self.namespace, self.user_id, account, revision, bundle]
        encoded = json.dumps(identity, sort_keys=True, ensure_ascii=True, allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _check_confirmation(self, kind, account, revision, bundle, confirmation, preview_token):
        if (confirmation != _CONFIRMATIONS[kind] or not isinstance(preview_token, str)
                or re.fullmatch(r"[a-f0-9]{64}", preview_token) is None):
            raise ValueError("Review the deletion scope and provide the exact confirmation and preview token.")
        expected = self._preview_token(kind, account, revision, bundle)
        if not hmac.compare_digest(preview_token, expected):
            raise StateConflict("Saved learner data changed or the deletion preview is invalid; review a new preview.")

    def preview_adaptation_erasure(self, *, account):
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account)
            model = bundle["models"].get(account)
            if model is not None:
                try:
                    validate_saved_learner_model(model, f"workspace:{account}")
                except LearnerStorageError as exc:
                    raise StateUnavailable("Private adaptation is invalid; deletion cannot be reviewed.") from exc
            sessions = bundle["state"].get("account_sessions", {})
            if not isinstance(sessions, dict) or any(not isinstance(item, dict) for item in sessions.values()):
                raise StateUnavailable("Saved account sessions are invalid; deletion cannot be reviewed.")
            pending = (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending"
            unsupported = model is not None and bool(set(model) - set(DEFAULT_LEARNER_MODEL))
            root = bundle["state"]
            session = sessions.get(account, {})
            return {"contract": "mammoth.learner-erasure.v1", "account_id": account, "revision": revision,
                    "preview_token": self._preview_token("adaptation", account, revision, bundle),
                    "scope": "active_account_private_model_and_adaptation_caches",
                    "model_status": "saved" if model is not None else "not_saved",
                    "pending_deletion": pending, "deletion_available": not unsupported,
                    "cached_fields": sorted(key for key in LEARNER_CACHE_FIELDS if key in root or key in session),
                    "deletion_blockers": ["unknown_model_extensions_require_review"] if unsupported else [],
                    "erases": ["private_model_onboarding_mastery_confidence_errors_outcomes_and_memory_graph",
                               "active_account_adaptation_caches"],
                    "excludes": list(LEARNER_ERASURE_EXCLUDES),
                    "cancels_tracked_account_requests": True, "provider_work_may_continue": True,
                    "fresh_activity_can_create_new_adaptation": True}

    def preview_learning_erasure(self, *, account):
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account)
            sessions = bundle["state"].get("account_sessions", {})
            if not isinstance(sessions, dict) or any(not isinstance(item, dict) for item in sessions.values()):
                raise StateUnavailable("Saved account sessions are invalid; deletion cannot be reviewed.")
            draft = bundle["drafts"].get(account)
            if draft is not None:
                try:
                    validate_workspace_record(draft)
                except WorkspaceStorageError as exc:
                    raise StateUnavailable("Saved workspace is invalid; deletion cannot be reviewed.") from exc
            return {"contract": "mammoth.learning-erasure.v1", "account_id": account, "revision": revision,
                    "preview_token": self._preview_token("learning", account, revision, bundle),
                    "scope": "active_account_saved_lesson_session_and_recovery",
                    "excludes": list(LEARNING_ERASURE_EXCLUDES)}

    def _save_locked(self, connection, bundle, revision):
        encoded = [json.dumps(bundle[key], ensure_ascii=True, allow_nan=False)
                   for key in ("state", "drafts", "models")]
        row = connection.execute(
            "UPDATE public.mammoth_learner_bundles SET state=%s::jsonb,drafts=%s::jsonb,"
            "models=%s::jsonb,revision=revision+1 WHERE namespace=%s AND user_id=%s "
            "AND revision=%s RETURNING revision",
            (*encoded, self.namespace, self.user_id, revision),
        ).fetchone()
        if row is None:
            raise StateConflict("Saved learner data changed; no update was confirmed.")
        return row[0]

    def _cancel_account(self, connection, account):
        connection.execute(
            "UPDATE public.mammoth_learning_operations SET status='cancellation_requested' "
            "WHERE namespace=%s AND user_id=%s AND account_id=%s AND status='running'",
            (self.namespace, self.user_id, account),
        )

    def _account_collections(self, state, account):
        accounts, sessions = state.get("accounts"), state.get("account_sessions")
        if (not isinstance(accounts, dict) or not isinstance(sessions, dict)
                or any(not isinstance(value, dict) for value in accounts.values())
                or any(not isinstance(value, dict) for value in sessions.values())
                or any(not isinstance(key, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) is None
                       for key in (*accounts, *sessions))):
            raise StateUnavailable("Saved account collections are invalid; no change was confirmed.")
        if account not in accounts:
            raise StateUnavailable("The active account is missing; no change was confirmed.")
        return accounts, sessions

    def _account_view(self, state):
        account = _active_account(state)
        accounts, _ = self._account_collections(state, account)
        visible = {}
        for account_id, value in accounts.items():
            profile = value.get("profile")
            if (not isinstance(profile, dict)
                    or any(key in profile and not isinstance(profile[key], str)
                           for key in ("display_name", "email", "organization"))
                    or not isinstance(value.get("tier"), str)
                    or value["tier"] not in {"explorer", "pro", "enterprise"}
                    or type(value.get("developer_access")) is not bool
                    or any(value.get(key) is not None and not isinstance(value[key], str)
                           for key in ("created_at", "updated_at", "profile_updated_at", "tier_updated_at",
                                       "developer_access_updated_at"))):
                raise StateUnavailable("Saved account profile is invalid; no data was returned.")
            visible[account_id] = {
                "profile": {key: profile.get(key, "") for key in ("display_name", "email", "organization")},
                "tier": value["tier"], "developer_access": value["developer_access"],
                "created_at": value.get("created_at"), "updated_at": value.get("updated_at"),
                "profile_updated_at": value.get("profile_updated_at"),
                "tier_updated_at": value.get("tier_updated_at"),
                "developer_access_updated_at": value.get("developer_access_updated_at"),
            }
        return {"active_account_id": account, "accounts": visible, "account_sessions": {}}

    def read_account_view(self):
        """Return account metadata and revision without exposing sessions or models."""
        with self._transaction() as connection:
            bundle, revision = self._locked_owner_snapshot(connection)
            return self._account_view(bundle["state"]), revision

    def update_account_metadata(self, *, revision, account, guard, changes, action, updated_at):
        allowed = {"profile", "tier", "developer_access"}
        if (not isinstance(changes, dict) or not changes or not set(changes).issubset(allowed)
                or not isinstance(action, str) or not action
                or not isinstance(updated_at, str) or not updated_at):
            raise ValueError("A supported account metadata update and timestamp are required.")
        if "profile" in changes:
            profile = changes["profile"]
            if (not isinstance(profile, dict) or set(profile) != {"display_name", "email", "organization"}
                    or any(not isinstance(value, str) for value in profile.values())):
                raise ValueError("A complete account profile is required.")
        if "tier" in changes and changes["tier"] not in {"explorer", "pro", "enterprise"}:
            raise ValueError("A supported entitlement tier is required.")
        if "developer_access" in changes and type(changes["developer_access"]) is not bool:
            raise ValueError("Developer access must be boolean.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            state = bundle["state"]
            if guard != self._approval_guard(state, account):
                raise StateConflict("Account state changed; reload before updating account metadata.")
            accounts, _ = self._account_collections(state, account)
            current = accounts[account]
            for key, value in changes.items():
                current[key] = deepcopy(value)
                if key == "profile":
                    current["profile_updated_at"] = updated_at
                    state["account_profile"] = deepcopy(value)
                    state["account_profile_updated_at"] = updated_at
                elif key == "tier":
                    current["tier_updated_at"] = updated_at
                    state["tier"] = value
                    state["tier_updated_at"] = updated_at
                else:
                    current["developer_access_updated_at"] = updated_at
                    state["developer_access"] = value
                    state["developer_access_updated_at"] = updated_at
            current["updated_at"] = updated_at
            state["updated_at"] = updated_at
            audit = state.setdefault("account_metadata_audit", [])
            if not isinstance(audit, list) or any(not isinstance(item, dict) for item in audit):
                raise StateUnavailable("Account metadata audit history is invalid; no update was saved.")
            audit.append({
                "account_id": account, "action": action,
                "fields": sorted(changes), "timestamp": updated_at,
            })
            state["account_metadata_audit"] = audit[-250:]
            try:
                _validate_bundle(bundle)
                view = self._account_view(state)
            except ValueError as exc:
                raise ValueError("Account metadata must contain valid JSON.") from exc
            new_revision = self._save_locked(connection, bundle, revision)
        return new_revision, view

    def _switch_locked(self, connection, state, account, target, *, preserve_departing=True):
        accounts, sessions = self._account_collections(state, account)
        if target not in accounts:
            raise StateConflict("The requested account is unavailable; reload before switching.")
        if target == account:
            return False
        destination = accounts[target]
        profile = destination.get("profile")
        if (not isinstance(profile, dict) or not isinstance(destination.get("tier"), str)
                or destination["tier"] not in {"explorer", "pro", "enterprise"}
                or type(destination.get("developer_access")) is not bool):
            raise StateUnavailable("Target account profile is invalid; no switch was confirmed.")
        if preserve_departing:
            previous = sessions.setdefault(account, {})
            for key in ACCOUNT_SESSION_FIELDS:
                if key in state:
                    previous[key] = deepcopy(state[key])
                else:
                    previous.pop(key, None)
        for key in ACCOUNT_SESSION_FIELDS:
            state.pop(key, None)
        for key, value in sessions.get(target, {}).items():
            if key in ACCOUNT_SESSION_FIELDS and key not in LEARNER_CACHE_FIELDS:
                state[key] = deepcopy(value)
        state["active_account_id"] = target
        state["user_id"] = f"workspace:{target}"
        state["account_profile"] = deepcopy(profile)
        state["tier"] = destination["tier"]
        state["developer_access"] = destination["developer_access"]
        for field in ("profile_updated_at", "tier_updated_at", "developer_access_updated_at"):
            name = "account_profile_updated_at" if field == "profile_updated_at" else field
            state[name] = destination.get(field)
        state["learning_account_epoch"] = uuid.uuid4().hex
        self._cancel_account(connection, account)
        return True

    def switch_account(self, *, revision, account, target, include_view=False):
        if not isinstance(target, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", target) is None:
            raise ValueError("A canonical target account ID is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            if not self._switch_locked(connection, bundle["state"], account, target):
                return (revision, self._account_view(bundle["state"])) if include_view else revision
            bundle["state"]["account_collections_epoch"] = uuid.uuid4().hex
            view = self._account_view(bundle["state"]) if include_view else None
            new_revision = self._save_locked(connection, bundle, revision)
            return (new_revision, view) if include_view else new_revision

    def create_account(self, *, revision, account, target, profile, created_at, activate=True, include_view=False):
        if not isinstance(target, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", target) is None:
            raise ValueError("A canonical target account ID is required.")
        if (not isinstance(profile, dict) or set(profile) != {"display_name", "email", "organization"}
                or any(not isinstance(value, str) for value in profile.values())
                or not profile["display_name"].strip() or not isinstance(created_at, str) or not created_at
                or type(activate) is not bool):
            raise ValueError("A valid account profile, creation timestamp and activation flag are required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            state = bundle["state"]
            accounts, sessions = self._account_collections(state, account)
            if target in accounts:
                raise StateConflict("The requested account already exists; reload before retrying.")
            if target in sessions:
                raise StateConflict("An unassigned saved session requires review before creating this account.")
            accounts[target] = {"profile": deepcopy(profile), "tier": "explorer", "developer_access": False,
                                "created_at": created_at, "updated_at": created_at,
                                "profile_updated_at": created_at}
            sessions[target] = {"status": "no_session", "updated_at": created_at}
            if activate:
                self._switch_locked(connection, state, account, target)
            state["updated_at"] = created_at
            state["account_collections_epoch"] = uuid.uuid4().hex
            view = self._account_view(state) if include_view else None
            new_revision = self._save_locked(connection, bundle, revision)
            return (new_revision, view) if include_view else new_revision

    def delete_account(self, *, revision, account, target, deleted_at, include_view=False):
        if not isinstance(target, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", target) is None:
            raise ValueError("A canonical target account ID is required.")
        if not isinstance(deleted_at, str) or not deleted_at:
            raise ValueError("A deletion timestamp is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            state = bundle["state"]
            accounts, sessions = self._account_collections(state, account)
            if target not in accounts:
                raise StateConflict("The requested account is unavailable; reload before deleting.")
            if len(accounts) <= 1:
                raise StateConflict("At least one workspace account must remain.")
            if target == account:
                replacement = sorted(key for key in accounts if key != target)[0]
                self._switch_locked(connection, state, account, replacement, preserve_departing=False)
            else:
                self._cancel_account(connection, target)
            del accounts[target]
            sessions.pop(target, None)
            state["updated_at"] = deleted_at
            state["account_collections_epoch"] = uuid.uuid4().hex
            view = self._account_view(state) if include_view else None
            new_revision = self._save_locked(connection, bundle, revision)
            return (new_revision, view) if include_view else new_revision

    def _require_live_operation(self, connection, bundle, account, operation_id):
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("A tracked learner operation is required.")
        operation = connection.execute(
            "SELECT o.status,o.account_id,f.fence FROM public.mammoth_learning_operations o "
            "LEFT JOIN public.mammoth_learner_operation_fences f "
            "ON f.namespace=o.namespace AND f.user_id=o.user_id AND f.operation_id=o.id "
            "WHERE o.namespace=%s AND o.user_id=%s AND o.id=%s FOR UPDATE OF o",
            (self.namespace, self.user_id, operation_id),
        ).fetchone()
        if (operation is None or operation[0] != "running" or operation[1] != account
                or operation[2] != _operation_fence(bundle["state"], account)):
            raise StateConflict("The learner operation is missing, cancelled, stale or belongs to another account.")

    def _session_fields(self, bundle, account):
        sessions = bundle["state"].get("account_sessions", {})
        if not isinstance(sessions, dict) or any(not isinstance(item, dict) for item in sessions.values()):
            raise StateUnavailable("Saved account sessions are invalid; no state change was confirmed.")
        session = sessions.get(account, {})
        return {key: bundle["state"].get(key, session.get(key))
                for key in _LEARNING_SESSION_FIELDS if key in bundle["state"] or key in session}

    def _approval_guard(self, state, account):
        return {"contract": "mammoth.learner-approval-fence.v1", "namespace": self.namespace,
                "owner": self.user_id, "account": account, "fence": _operation_fence(state, account)}

    def _learner_approvals(self, state):
        approvals = state.setdefault("learner_approvals", [])
        if not isinstance(approvals, list) or len(approvals) > _LEARNER_APPROVAL_AUDIT_LIMIT:
            raise StateUnavailable("Saved learner approvals are invalid; no approval action was performed.")
        seen = set()
        for item in approvals:
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                    or not item["id"] or item["id"] in seen
                    or item.get("operation") not in _LEARNER_APPROVAL_OPERATIONS
                    or not isinstance(item.get("account_id"), str)
                    or item.get("status") not in {"pending", "approved", "deleted"}
                    or not isinstance(item.get("payload"), dict)
                    or not isinstance(item.get("preview"), dict)
                    or not isinstance(item.get("learner_write_guard"), dict)
                    or not isinstance(item.get("requested_by"), str)
                    or not item["requested_by"]
                    or not isinstance(item.get("created_at"), str)
                    or not item["created_at"]):
                raise StateUnavailable("Saved learner approvals are invalid; no approval action was performed.")
            seen.add(item["id"])
        return approvals

    def _append_learner_approval_audit(self, state, record, action, actor):
        audit = state.setdefault("learner_approval_audit", [])
        if not isinstance(audit, list) or any(not isinstance(item, dict) for item in audit):
            raise StateUnavailable("Saved learner approval audit is invalid; no approval action was performed.")
        audit.append({
            "approval_id": record["id"], "operation": record["operation"],
            "account_id": record["account_id"], "action": action,
            "actor": actor, "created_at": _now_iso(),
        })
        state["learner_approval_audit"] = audit[-_LEARNER_APPROVAL_AUDIT_LIMIT:]

    def create_learner_approval(self, *, revision, account, approval_guard, record):
        if (not isinstance(record, dict) or record.get("operation") not in _LEARNER_APPROVAL_OPERATIONS
                or not isinstance(record.get("id"), str) or not record["id"]
                or not isinstance(record.get("task_id"), str) or not record["task_id"]
                or not isinstance(record.get("preview"), dict)
                or not isinstance(record.get("payload"), dict)
                or not isinstance(record.get("requested_by"), str) or not record["requested_by"]
                or not isinstance(record.get("target"), str) or not record["target"]
                or not isinstance(record.get("created_at"), str) or not record["created_at"]
                or record.get("learner_write_guard") != approval_guard):
            raise ValueError("A supported learner approval record is required.")
        operation = record["operation"]
        payload = record["payload"]
        if operation == "atlas_onboard_update":
            onboarding = payload.get("onboarding")
            if not isinstance(onboarding, dict) or set(payload) != {"onboarding"}:
                raise ValueError("A valid onboarding approval payload is required.")
        elif payload:
            raise ValueError("Reset approvals must not contain a payload.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            state = bundle["state"]
            if (_erasure_records(state).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; no learner approval was created.")
            if approval_guard != self._approval_guard(state, account):
                raise StateConflict("Learner data changed while approval was being prepared; request a new approval.")
            approvals = self._learner_approvals(state)
            if any(item.get("id") == record["id"] for item in approvals):
                raise StateConflict("Learner approval identifier already exists.")
            stored = deepcopy(record)
            stored.update({"account_id": account, "status": "pending"})
            approvals.append(stored)
            state["learner_approvals"] = approvals[-_LEARNER_APPROVAL_AUDIT_LIMIT:]
            self._append_learner_approval_audit(state, stored, "requested", stored["requested_by"])
            self._save_locked(connection, bundle, revision)
        return stored

    def read_learner_approvals(self):
        with self._transaction() as connection:
            bundle, _ = self._locked_owner_snapshot(connection)
            return deepcopy(self._learner_approvals(bundle["state"]))

    def approve_learner_approval(self, *, record_id, actor):
        if not isinstance(record_id, str) or not record_id or not isinstance(actor, str) or not actor:
            raise ValueError("A learner approval ID and actor are required.")
        with self._transaction() as connection:
            bundle, revision = self._locked_owner_snapshot(connection)
            state = bundle["state"]
            approvals = self._learner_approvals(state)
            record = next((item for item in approvals if item.get("id") == record_id), None)
            if record is None:
                return {"status": "error", "message": "approval not found"}
            if record.get("status") == "approved":
                return {"status": "ok", "approval": deepcopy(record),
                        "result": deepcopy(record.get("last_result"))}
            if record.get("status") != "pending":
                raise StateConflict("Learner approval is no longer pending; unknown actions are never replayed.")
            account = record.get("account_id")
            if not isinstance(account, str) or _active_account(state) != account:
                raise StateConflict("Learner account changed; request a new approval before retrying.")
            if (_erasure_records(state).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; approval was not executed.")
            if record.get("learner_write_guard") != self._approval_guard(state, account):
                raise StateConflict("Learner approval is stale; request a new approval.")

            operation = record.get("operation")
            if operation == "atlas_onboard_update":
                onboarding = record.get("payload", {}).get("onboarding")
                if not isinstance(onboarding, dict):
                    raise StateUnavailable("Saved onboarding approval is invalid; no action was performed.")
                self._session_fields(bundle, account)
                model = self._model_for_update(bundle, account)
                _apply_onboarding_profile(model, onboarding)
                model["last_updated"] = _now_iso()
                try:
                    validate_saved_learner_model(model, f"workspace:{account}")
                except LearnerStorageError as exc:
                    raise ValueError("The onboarding approval produced invalid private adaptation.") from exc
                self._store_model_caches(bundle, account, model)
                result = {"status": "ok", "message": "Onboarding update approved and applied."}
            elif operation in {"atlas_learner_reset", "atlas_session_reset"}:
                session_reset = operation == "atlas_session_reset"
                self._apply_reset_to_bundle(
                    connection, bundle, account, session_reset=session_reset, saved_at=_now_iso(),
                )
                result = {"status": "ok", "message": "Learner reset approved and applied."}
            else:
                raise StateUnavailable("Saved learner approval operation is unsupported; no action was performed.")

            now = _now_iso()
            record.update({
                "status": "approved", "approved_by": actor, "approved_at": now,
                "completed_at": now, "last_result": deepcopy(result),
            })
            state["learner_approvals"] = approvals
            self._append_learner_approval_audit(state, record, "approved", actor)
            self._save_locked(connection, bundle, revision)
            return {"status": "ok", "approval": deepcopy(record), "result": result}

    def delete_learner_approval(self, *, record_id, actor, reason="deleted_by_user"):
        if (not isinstance(record_id, str) or not record_id or not isinstance(actor, str) or not actor
                or not isinstance(reason, str) or not reason):
            raise ValueError("A learner approval ID, actor and reason are required.")
        with self._transaction() as connection:
            bundle, revision = self._locked_owner_snapshot(connection)
            state = bundle["state"]
            approvals = self._learner_approvals(state)
            record = next((item for item in approvals if item.get("id") == record_id), None)
            if record is None:
                return {"status": "error", "message": "approval not found"}
            if record.get("status") != "pending":
                raise StateConflict("Only pending learner approvals can be discarded.")
            record.update({
                "status": "deleted", "deleted_by": actor, "deleted_at": _now_iso(),
                "delete_reason": reason,
            })
            self._append_learner_approval_audit(state, record, "deleted", actor)
            state["learner_approvals"] = approvals
            self._save_locked(connection, bundle, revision)
            return {"status": "ok", "approval": deepcopy(record)}

    def read_approval_guard(self, *, account):
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; no learner approval was issued.")
            return self._approval_guard(bundle["state"], account), revision

    def _model_for_update(self, bundle, account):
        user_id = f"workspace:{account}"
        previous = bundle["models"].get(account)
        if previous is not None:
            try:
                validate_saved_learner_model(previous, user_id)
            except LearnerStorageError as exc:
                raise StateUnavailable("Saved private adaptation is invalid; no update was saved.") from exc
        return _ensure_model_shape(deepcopy(previous), user_id)

    def _store_model_caches(self, bundle, account, model, topic=None, *, use_state_topic=True):
        state = bundle["state"]
        session = state.setdefault("account_sessions", {}).setdefault(account, {})
        context = build_learner_context(model, topic=(topic or state.get("topic")) if use_state_topic else topic)
        caches = {
            "learner_model": model,
            "learner_context": context,
            "learner_storage": learner_storage_scope(self.user_id, f"workspace:{account}"),
            "learner_profile": {
                "streak": context.get("streak", 0), "attempts": context.get("attempts", 0),
                "recommended_difficulty": context.get("recommended_difficulty", "beginner"),
                "preferred_pacing": context.get("preferred_pacing", "gentle"),
            },
        }
        for key, value in caches.items():
            state[key] = deepcopy(value)
            session[key] = deepcopy(value)
        bundle["models"][account] = model

    def update_onboarding(self, *, revision, account, approval_guard, onboarding):
        if not isinstance(onboarding, dict):
            raise ValueError("An onboarding profile object is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; onboarding was not saved.")
            if approval_guard != self._approval_guard(bundle["state"], account):
                raise StateConflict("Learner approval is unbound or stale; request a new approval.")
            self._session_fields(bundle, account)
            model = self._model_for_update(bundle, account)
            _apply_onboarding_profile(model, onboarding)
            model["last_updated"] = _now_iso()
            try:
                validate_saved_learner_model(model, f"workspace:{account}")
            except LearnerStorageError as exc:
                raise ValueError("The onboarding profile produced invalid private adaptation.") from exc
            self._store_model_caches(bundle, account, model)
            try:
                _validate_bundle(bundle)
            except ValueError as exc:
                raise ValueError("The onboarding profile must contain valid JSON.") from exc
            new_revision = self._save_locked(connection, bundle, revision)
        return new_revision

    def reset_learner(self, *, revision, account, approval_guard, session_reset, saved_at):
        if type(session_reset) is not bool or not isinstance(saved_at, str) or not saved_at:
            raise ValueError("A reset type and saved timestamp are required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            state = bundle["state"]
            if (_erasure_records(state).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; reset was not saved.")
            if approval_guard != self._approval_guard(state, account):
                raise StateConflict("Learner approval is unbound or stale; request a new approval.")
            self._apply_reset_to_bundle(
                connection, bundle, account, session_reset=session_reset, saved_at=saved_at,
            )
            new_revision = self._save_locked(connection, bundle, revision)
        return new_revision

    def _apply_reset_to_bundle(self, connection, bundle, account, *, session_reset, saved_at):
        state = bundle["state"]
        self._session_fields(bundle, account)
        previous = self._workspace_snapshot(bundle, account)
        model = _reset_model_progress(self._model_for_update(bundle, account))
        model["last_updated"] = _now_iso()
        workspace_epoch = uuid.uuid4().hex
        state["workspace_epoch"] = workspace_epoch
        state["learning_reset_epoch"] = uuid.uuid4().hex
        session = state.setdefault("account_sessions", {}).setdefault(account, {})
        session["workspace_epoch"] = workspace_epoch
        if session_reset:
            state["status"] = session["status"] = "reset"
        state.pop("lesson_telemetry", None)
        session.pop("lesson_telemetry", None)
        self._store_model_caches(bundle, account, model, use_state_topic=False)
        profile = {"streak": 0, "attempts": 0, "recommended_difficulty": "beginner",
                   "preferred_pacing": "gentle"}
        state["learner_profile"] = deepcopy(profile)
        session["learner_profile"] = deepcopy(profile)
        fresh = self._workspace_snapshot({**bundle, "drafts": {}}, account)
        bundle["drafts"][account] = {
            "exercise_key": workspace_content_key(state), "revision": previous["revision"] + 1,
            "values": fresh["values"], "saved_at": saved_at,
        }
        self._cancel_account(connection, account)

    def read_learning_session(self, *, account, revision=None):
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account, revision)
            return self._session_fields(bundle, account), revision

    def read_status_snapshot(self):
        """Read one consistent active-account status, model and recovery snapshot."""
        with self._transaction() as connection:
            bundle, revision = self._locked_owner_snapshot(connection)
            account = _active_account(bundle["state"])
            self._account_collections(bundle["state"], account)
            state = bundle["state"]
            session = state.get("account_sessions", {}).get(account, {})
            fields = {
                key: deepcopy(state.get(key, session.get(key)))
                for key in ACCOUNT_SESSION_FIELDS
                if key in state or key in session
            }
            metadata = self._account_view(state)["accounts"][account]
            erasure = _erasure_records(state).get(account)
            if (erasure or {}).get("status") == "pending":
                raise StateUnavailable("Private adaptation deletion is pending; learner status is temporarily unavailable.")
            model = bundle["models"].get(account)
            if model is not None:
                try:
                    validate_saved_learner_model(model, f"workspace:{account}")
                except LearnerStorageError as exc:
                    raise StateUnavailable("Saved private adaptation is invalid; no status was returned.") from exc
                model = {key: deepcopy(model[key]) for key in DEFAULT_LEARNER_MODEL if key in model}
            workspace = self._workspace_snapshot(bundle, account)
            return {
                "account_id": account, "session": fields, "account": metadata,
                "model": model, "workspace_recovery": workspace,
            }, revision

    def _workspace_collections(self, state, account):
        _, sessions = self._account_collections(state, account)
        session = sessions.get(account, {})
        values = {}
        for key, limit in _WORKSPACE_COLLECTION_LIMITS.items():
            value = state.get(key, session.get(key, []))
            if (not isinstance(value, list) or len(value) > limit
                    or any(not isinstance(item, dict) for item in value)):
                raise StateUnavailable("Saved workspace collections are invalid; no data was returned.")
            if key == "curriculum_library":
                seen = set()
                for item in value:
                    curriculum = item.get("curriculum")
                    curriculum_id = curriculum.get("curriculum_id") if isinstance(curriculum, dict) else None
                    try:
                        encoded_size = len(json.dumps(curriculum, ensure_ascii=True).encode("utf-8"))
                    except (TypeError, ValueError, RecursionError) as exc:
                        raise StateUnavailable(
                            "Saved curriculum library is invalid; no data was returned.",
                        ) from exc
                    if (not isinstance(curriculum_id, str) or not curriculum_id or curriculum_id in seen
                            or not isinstance(item.get("saved_at"), str) or not item["saved_at"]
                            or encoded_size > 2_000_000):
                        raise StateUnavailable("Saved curriculum library is invalid; no data was returned.")
                    seen.add(curriculum_id)
            values[key] = deepcopy(value)
        return values

    def read_workspace_collections(self, *, account):
        """Return only the active account's supported workspace collections."""
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account)
            state = bundle["state"]
            return self._workspace_collections(state, account), self._approval_guard(state, account), revision

    def update_workspace_collection(self, *, revision, account, guard, field, values, updated_at):
        """Revision-check an account-scoped collection without exposing raw state writes."""
        if (not isinstance(field, str) or field not in _WORKSPACE_COLLECTION_LIMITS
                or not isinstance(values, list) or len(values) > _WORKSPACE_COLLECTION_LIMITS[field]
                or any(not isinstance(item, dict) for item in values)
                or (updated_at is not None and (not isinstance(updated_at, str) or not updated_at))):
            raise ValueError("A supported workspace collection and optional update timestamp are required.")
        if field == "curriculum_library":
            seen = set()
            for item in values:
                curriculum = item.get("curriculum")
                curriculum_id = curriculum.get("curriculum_id") if isinstance(curriculum, dict) else None
                try:
                    encoded_size = len(json.dumps(curriculum, ensure_ascii=True).encode("utf-8"))
                except (TypeError, ValueError, RecursionError) as exc:
                    raise ValueError("A valid bounded curriculum library is required.") from exc
                if (not isinstance(curriculum_id, str) or not curriculum_id or curriculum_id in seen
                        or not isinstance(item.get("saved_at"), str) or not item["saved_at"]
                        or encoded_size > 2_000_000):
                    raise ValueError("A valid bounded curriculum library is required.")
                seen.add(curriculum_id)
        values = deepcopy(values)
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            state = bundle["state"]
            self._workspace_collections(state, account)
            if guard != self._approval_guard(state, account):
                raise StateConflict("Workspace account or learner state changed; reload before saving.")
            session = state.setdefault("account_sessions", {}).setdefault(account, {})
            state[field] = deepcopy(values)
            session[field] = values
            if updated_at is not None:
                state["updated_at"] = session["updated_at"] = updated_at
            try:
                _validate_bundle(bundle)
            except ValueError as exc:
                raise ValueError("Workspace collections must contain valid JSON.") from exc
            return self._save_locked(connection, bundle, revision)

    def update_learning_session(self, *, revision, account, operation_id, changes, remove=()):
        if (not isinstance(changes, dict) or not isinstance(remove, (list, tuple))
                or any(not isinstance(key, str) for key in changes)
                or any(not isinstance(key, str) for key in remove)
                or len(set(remove)) != len(remove)
                or not set(changes).issubset(_LEARNING_SESSION_FIELDS)
                or not set(remove).issubset(_LEARNING_SESSION_FIELDS)
                or set(changes).intersection(remove)):
            raise ValueError("Only supported, non-overlapping learning session fields may be changed.")
        if not changes and not remove:
            raise ValueError("At least one learning session change is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; no state was saved.")
            self._session_fields(bundle, account)
            self._require_live_operation(connection, bundle, account, operation_id)
            state = bundle["state"]
            sessions = state.setdefault("account_sessions", {})
            session = sessions.setdefault(account, {})
            for key in remove:
                state.pop(key, None)
                session.pop(key, None)
            for key, value in changes.items():
                state[key] = value
                session[key] = value
            try:
                _validate_bundle(bundle)
            except ValueError as exc:
                raise ValueError("Learning session changes must contain valid JSON.") from exc
            new_revision = self._save_locked(connection, bundle, revision)
            result = self._session_fields(bundle, account)
        return result, new_revision

    def begin_operation(self, *, revision, account, route):
        if not isinstance(route, str) or not route:
            raise ValueError("A learning operation route is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; no operation was started.")
            controls = PostgresLearningControls(self.dsn, self.namespace, self.user_id)
            operation_id = controls._begin_in_transaction(connection, route, account)
            connection.execute(
                "INSERT INTO public.mammoth_learner_operation_fences(namespace,user_id,operation_id,fence) "
                "VALUES(%s,%s,%s,%s::jsonb)",
                (self.namespace, self.user_id, operation_id,
                 json.dumps(_operation_fence(bundle["state"], account), ensure_ascii=True, allow_nan=False)),
            )
            return operation_id

    def _active_workspace_state(self, bundle, account):
        state = deepcopy(bundle["state"])
        state["active_account_id"] = account
        session = state.get("account_sessions", {}).get(account, {})
        for key in ACCOUNT_SESSION_FIELDS:
            if key not in state and key in session:
                state[key] = deepcopy(session[key])
        return state

    def _workspace_snapshot(self, bundle, account):
        saved = bundle["drafts"].get(account)
        if saved is not None:
            try:
                validate_workspace_record(saved)
            except WorkspaceStorageError as exc:
                raise StateUnavailable("Saved workspace is invalid; no draft was changed.") from exc
        try:
            state = self._active_workspace_state(bundle, account)
            return workspace_snapshot(state, saved)
        except (TypeError, AttributeError, ValueError) as exc:
            raise StateUnavailable("Saved exercise is invalid; no draft was changed.") from exc

    def read_workspace(self, *, account, revision=None):
        with self._transaction() as connection:
            bundle, revision = self._locked_snapshot(connection, account, revision)
            return self._workspace_snapshot(bundle, account), revision

    def save_draft(self, *, revision, account, exercise_key, draft_revision, values, saved_at):
        validate_workspace_values(values)
        if type(draft_revision) is not int or draft_revision < 0:
            raise ValueError("A nonnegative draft revision is required.")
        if not isinstance(saved_at, str) or not saved_at:
            raise ValueError("A saved timestamp is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            current = self._workspace_snapshot(bundle, account)
            if exercise_key != current["exercise_key"] or draft_revision != current["revision"]:
                raise StateConflict("The exercise or draft changed; reload before saving.")
            state = self._active_workspace_state(bundle, account)
            record = {**bundle["drafts"].get(account, {}),
                      "exercise_key": workspace_content_key(state),
                      "revision": current["revision"] + 1,
                      "values": values, "saved_at": saved_at}
            bundle["drafts"][account] = record
            new_revision = self._save_locked(connection, bundle, revision)
        return workspace_snapshot(state, record), new_revision

    def clear_draft(self, *, revision, account, exercise_key, draft_revision, saved_at):
        if type(draft_revision) is not int or draft_revision < 0:
            raise ValueError("A nonnegative draft revision is required.")
        if not isinstance(saved_at, str) or not saved_at:
            raise ValueError("A saved timestamp is required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            current = self._workspace_snapshot(bundle, account)
            if exercise_key != current["exercise_key"] or draft_revision != current["revision"]:
                raise StateConflict("The exercise or draft changed; reload before clearing.")
            fresh = self._workspace_snapshot({**bundle, "drafts": {}}, account)
            state = self._active_workspace_state(bundle, account)
            record = {"exercise_key": workspace_content_key(state),
                      "revision": current["revision"] + 1,
                      "values": fresh["values"], "saved_at": saved_at}
            bundle["drafts"][account] = record
            new_revision = self._save_locked(connection, bundle, revision)
        return workspace_snapshot(state, record), new_revision

    def confirm_adaptation_erasure(self, *, revision, account, confirmation, preview_token):
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            self._check_confirmation("adaptation", account, revision, bundle, confirmation, preview_token)
            state = bundle["state"]
            records = _erasure_records(state)
            model = bundle["models"].get(account)
            if model is not None:
                try:
                    validate_saved_learner_model(model, f"workspace:{account}")
                except LearnerStorageError as exc:
                    raise StateUnavailable("Private adaptation is invalid; no deletion was confirmed.") from exc
                if set(model) - set(DEFAULT_LEARNER_MODEL):
                    raise StateConflict("Unknown model extensions require review before deletion.")
            sessions = state.get("account_sessions", {})
            if not isinstance(sessions, dict) or any(not isinstance(item, dict) for item in sessions.values()):
                raise StateUnavailable("Saved account sessions are invalid; no deletion was confirmed.")
            epoch = uuid.uuid4().hex
            for key in LEARNER_CACHE_FIELDS:
                state.pop(key, None)
                if account in sessions:
                    sessions[account].pop(key, None)
            state["learner_erasure"] = {**records, account: {"epoch": epoch, "status": "complete"}}
            bundle["models"].pop(account, None)
            self._cancel_account(connection, account)
            new_revision = self._save_locked(connection, bundle, revision)
        return epoch, new_revision

    def confirm_learning_erasure(self, *, revision, account, confirmation, preview_token):
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            self._check_confirmation("learning", account, revision, bundle, confirmation, preview_token)
            state = bundle["state"]
            sessions = state.get("account_sessions", {})
            if not isinstance(sessions, dict) or any(not isinstance(item, dict) for item in sessions.values()):
                raise StateUnavailable("Saved account sessions are invalid; no deletion was confirmed.")
            draft = bundle["drafts"].get(account)
            if draft is not None:
                try:
                    validate_workspace_record(draft)
                except WorkspaceStorageError as exc:
                    raise StateUnavailable("Saved workspace is invalid; no deletion was confirmed.") from exc
            epoch, workspace_epoch = uuid.uuid4().hex, uuid.uuid4().hex
            for key in ERASABLE_LEARNING_FIELDS:
                state.pop(key, None)
            state["status"] = "no_session"
            state["workspace_epoch"] = workspace_epoch
            state["learning_erasure_epoch"] = epoch
            if account not in sessions:
                sessions[account] = {}
            for key in ERASABLE_LEARNING_FIELDS:
                sessions[account].pop(key, None)
            sessions[account].update(status="no_session", workspace_epoch=workspace_epoch)
            state["account_sessions"] = sessions
            bundle["drafts"].pop(account, None)
            self._cancel_account(connection, account)
            new_revision = self._save_locked(connection, bundle, revision)
        return epoch, new_revision

    def save_adaptation(self, *, revision, account, operation_id, model):
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("A tracked learner operation is required.")
        try:
            validate_saved_learner_model(model, f"workspace:{account}")
        except LearnerStorageError as exc:
            raise ValueError("The proposed private adaptation is invalid.") from exc
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; no model was saved.")
            previous = bundle["models"].get(account)
            if previous is not None:
                try:
                    validate_saved_learner_model(previous, f"workspace:{account}")
                except LearnerStorageError as exc:
                    raise StateUnavailable("Saved private adaptation is invalid; no model was overwritten.") from exc
                extensions = set(previous) - set(DEFAULT_LEARNER_MODEL)
                if any(key not in model or model[key] != previous[key] for key in extensions):
                    raise StateConflict("Unknown model extensions require review before modification.")
            self._require_live_operation(connection, bundle, account, operation_id)
            bundle["models"][account] = model
            new_revision = self._save_locked(connection, bundle, revision)
        return new_revision

    def record_learning_result(self, *, revision, account, operation_id, result,
                               changes, lesson=None, exercise=None, topic=None, metadata=None):
        if (not isinstance(result, dict) or not isinstance(changes, dict)
                or any(not isinstance(key, str) for key in changes)
                or not set(changes).issubset(_LEARNING_SESSION_FIELDS)
                or any(value is not None and not isinstance(value, dict)
                       for value in (lesson, exercise, metadata))
                or (topic is not None and not isinstance(topic, str))):
            raise ValueError("A learning result and supported session changes are required.")
        with self._transaction() as connection:
            bundle = self._locked_bundle(connection, revision, account)
            if (_erasure_records(bundle["state"]).get(account) or {}).get("status") == "pending":
                raise StateConflict("Private adaptation deletion is pending; no result was saved.")
            self._session_fields(bundle, account)
            self._require_live_operation(connection, bundle, account, operation_id)
            user_id = f"workspace:{account}"
            model = self._model_for_update(bundle, account)
            _apply_learning_result(model, lesson=lesson, exercise=exercise, result=result,
                                   topic=topic, metadata=metadata)
            model["last_updated"] = _now_iso()
            try:
                validate_saved_learner_model(model, user_id)
            except LearnerStorageError as exc:
                raise ValueError("The learning result produced invalid private adaptation.") from exc
            state = bundle["state"]
            session = state.setdefault("account_sessions", {}).setdefault(account, {})
            for key, value in changes.items():
                state[key] = deepcopy(value)
                session[key] = deepcopy(value)
            self._store_model_caches(bundle, account, model, topic=topic)
            try:
                _validate_bundle(bundle)
            except ValueError as exc:
                raise ValueError("Learning result changes must contain valid JSON.") from exc
            new_revision = self._save_locked(connection, bundle, revision)
        return new_revision
