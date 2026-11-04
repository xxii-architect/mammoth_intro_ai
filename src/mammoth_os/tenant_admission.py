"""Membership-checked shared completion admission; estimates are not invoices."""

import uuid

from .runtime_ledger import RuntimeLimitReached
from .shared_state import StateUnavailable, service_rpc


def memberships(user_id, rpc=None):
    rpc = rpc or service_rpc
    return rpc("mammoth_runtime_memberships", {"p_user": str(uuid.UUID(user_id))})


class TenantLedger:
    def __init__(self, user_id, tenant_id=None, *, rpc=None):
        self.user_id = str(uuid.UUID(user_id))
        self.tenant_id = str(uuid.UUID(tenant_id)) if tenant_id else None
        self.rpc = rpc or service_rpc

    def _tenant(self):
        if self.tenant_id is None:
            tenants = memberships(self.user_id, self.rpc).get("tenants", [])
            if len(tenants) != 1:
                raise StateUnavailable("Select an active tenant explicitly; no unique tenant is available.")
            self.tenant_id = str(uuid.UUID(tenants[0]["tenant_id"]))
        return self.tenant_id

    def _call(self, name, **params):
        result = self.rpc(name, {"p_user": self.user_id, "p_tenant": self._tenant(), **params})
        if result.get("error"):
            raise RuntimeLimitReached(f"Tenant admission refused: {result['error']}. No automatic retry was made.")
        return result

    def reserve(self, provider, model, tokens, *, input_tokens=None, output_tokens=None):
        if input_tokens is None or output_tokens is None or input_tokens + output_tokens != tokens:
            raise ValueError("Tenant admission requires separate input and output allowances.")
        identity = str(uuid.uuid4())
        result = self._call("mammoth_runtime_reserve", p_id=identity, p_provider=provider, p_model=model,
                            p_input=input_tokens, p_output=output_tokens)
        if result.get("admitted") is not True:
            raise StateUnavailable("Tenant reservation was not confirmed; no provider call was started.")
        return identity

    def finish(self, identity, *, usage=None, failed=False):
        result = self._call("mammoth_runtime_finish", p_id=identity, p_usage=usage or {}, p_failed=failed)
        if result.get("saved") is not True:
            raise StateUnavailable("Tenant settlement was not confirmed; the reservation remains retained.")

    def snapshot(self):
        return self._call("mammoth_runtime_usage")

    def set_limits(self, tokens, usd_micros):
        for value, maximum in ((tokens, 1_000_000_000), (usd_micros, 1_000_000_000_000)):
            if value is not None and (type(value) is not int or not 0 <= value <= maximum):
                raise ValueError("Limits must be null or bounded non-negative whole numbers.")
        result = self._call("mammoth_runtime_policy", p_tokens=tokens, p_usd_micros=usd_micros)
        if result.get("saved") is not True:
            raise StateUnavailable("Tenant policy was not confirmed.")
        return self.snapshot()


class CombinedLedger:
    """Keep the per-login ceiling additive to the shared tenant ceiling."""

    def __init__(self, private, tenant):
        self.private, self.tenant = private, tenant

    def reserve(self, provider, model, tokens, **allowances):
        private_id = self.private.reserve(provider, model, tokens, **allowances)
        try:
            tenant_id = self.tenant.reserve(provider, model, tokens, **allowances)
        except RuntimeLimitReached:
            # Definitive rejection before any provider call; not an unknown paid outcome.
            with self.private._db() as db:
                db.execute("DELETE FROM attempts WHERE id=? AND status='pending'", (private_id,))
            raise
        return private_id, tenant_id

    def finish(self, identity, **result):
        self.private.finish(identity[0], **result)
        self.tenant.finish(identity[1], **result)
