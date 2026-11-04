# Shared runtime operations

## What this release changes

Generic JSON collections (notes, tasks, approvals, activity, audit, feedback,
build log, sales, snapshots, generated-document ownership and eval history)
use a common read/modify/write store. Local saves are locked, atomic and fsynced.
Concurrent disjoint keyed records merge; competing edits are rejected, not
last-write-wins. An unkeyed collection cannot be safely merged and returns a
conflict. A 409 requires reloading and an explicit new decision, never blindly
retrying a side effect. Corrupt records produce 503 without resetting data.

Legacy approvals commit a unique `executing` claim before running an action.
Only pending approvals execute. A lost worker leaves a retained unknown outcome
that cannot be replayed or discarded automatically. Inspect external evidence
before deciding on a new, separately approved action.

Learner JSON remains local: its existing erasure/recovery locks and fences stay
in place, with added stale-write detection and explicit corruption errors.
It is **not** migrated by selecting the generic shared backend.

## Explicit storage cutover

Defaults remain local. No production migration is automatic.

1. Back up the database and private `.mammoth` directory; stop all writers.
2. Apply `.mammoth/supabase_tenant_auth.sql` only according to the existing
   deployment procedure, then the additive `supabase_runtime_state.sql` and
   `supabase_tenant_admission.sql`. The new operational tables/RPCs deny direct
   `anon`/`authenticated` access. They do not duplicate product tables.
3. Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` on the backend only.
   Never send the service key to a browser or SDK. Select a distinct
   alphanumeric/hyphen/underscore `MAMMOTH_STATE_NAMESPACE` per deployment.
4. For each reviewed generic record, run the explicit import while quiesced:

   ```powershell
   $env:PYTHONPATH="$PWD\src"
   python scripts\migrate_shared_state.py import --key production/notes.json --file .mammoth\notes.json --confirm-quiesced
   ```

   Keys preserve the original path relative to `.mammoth`, prefixed by the
   deployment namespace. Review existing ownership before importing; this tool
   never assigns old operator data to a new tenant. Existing backend records
   are refused, not overwritten.
5. Set `MAMMOTH_STATE_BACKEND=supabase`, then restart through the normal approved
   deployment process. A backend failure is a storage error, not local fallback.
6. Smoke-test authorized read/update/conflict behavior before reopening writes.
   Retain backups. To roll back, stop writers, export each latest backend record
   to a **new private file**, review it, then replace the local copy through the
   normal backup/restore procedure and select `local`. Do not switch to stale
   local files while shared writers remain active.

   ```powershell
   python scripts\migrate_shared_state.py export --key production/notes.json --file C:\private-backup\notes-restored.json
   ```

   Export refuses an existing output file. Keep backup directories private.

## Tenant-wide token and estimated-dollar admission

Set `MAMMOTH_USAGE_BACKEND=supabase` only after the migration and membership
checks pass. This is separate from selecting shared JSON storage. Both backends
are opt-in. The private login-wide SQLite ceiling remains additive.

Settings > Tenant usage controls lists only active memberships. Selecting a
tenant scopes subsequent UI requests with `X-Mammoth-Tenant-ID`; selection is
memory-only and keyed to the authenticated user. SDKs can send the same header.
New run checkpoints bind their tenant so continuation cannot silently charge a
different tenant. Without an explicit selection, exactly one active membership
is required. Owner/admin/member may generate; viewers may read usage only.
Only owners/admins can change limits, and policy changes are audit-logged.

Daily limits use the admission's UTC day. Empty means uncapped; zero blocks new
covered calls. `daily_usd_limit_micros` is an integer: 1 USD = 1,000,000 microUSD.
Reservations serialize at the tenant-policy row before any covered provider
attempt. Unknown/failed/interrupted outcomes retain the full allowance; there
is no automatic reservation expiry or paid replay. Identical settlements are
idempotent; inconsistent repeat settlements are rejected.

### Reviewed price catalog

An operator must populate `public.mammoth_runtime_prices` through the trusted
database administration path with the **exact** provider/model, a version,
source, expiry and integer input/output microUSD-per-million-token rates.
Use current provider documentation and the deployment's actual contract.
No prices are invented or bundled, and tenant members cannot edit prices.

For example, convert a verified input price of `P` USD per million tokens to
`P * 1000000` integer microUSD per million; output uses its own verified rate.
The reservation rounds the combined cost up to the next microUSD. Each attempt
pins the full price record; later catalog updates do not reprice old attempts.
There is deliberately no executable SQL sample containing placeholder prices.

An enabled dollar ceiling blocks missing/expired exact prices and any prior
unpriced admission that day. Uncapped unpriced attempts remain explicitly
unknown, not free. Reported input/output counts settle estimates; total-only
usage keeps at least the reservation and prices larger totals at the higher
rate. Missing/invalid counts retain the reservation. Reported overruns are
stored truthfully and can exceed a limit; future admissions then stop.
Limits cannot cancel or perfectly predict a provider's already-started call.

Coverage is hosted leaf calls through `llm_completion`, including standard
OpenAI/Ollama text adapters. Embeddings, uninstrumented/custom paid services,
provider-SDK internal retries, external SDK usage and invoices are not complete
accounting. Estimated USD is never presented as invoice-verified spend.

## Actual-host trusted container acceptance

Dispatch **Owner Container Acceptance** with `target=production`,
`image=configured` (or an explicitly reviewed digest) and
`pull_reviewed_image=false`. The protected production job uses existing
`DO_*` SSH secrets and requires pinned `DO_KNOWN_HOSTS`; it never keyscans.
It does not invoke the deployment command.

Preflight requires a running `mammothos` service, the expected checkout and the
same SSH/live-service UID. It uses the live process's Python and environment
without exposing environment contents. The reviewed branch's trusted acceptance harness is staged only in a temporary
directory and imports the **deployed** executor, using an already-cached reviewed
digest. This allows harness fixes to be tested without deploying runtime code.
No deploy, image pull,
service restart, policy loosening or host fallback occurs.

The `mammoth.hosted-container-evidence.v1` receipt binds the deployed commit,
deployed executor hash, deployed/candidate probe hashes, reviewed image and nested
strict container receipt. A failure or
missing precondition remains `not_verified`; a green runner-only probe cannot
substitute for actual-host evidence. Even a verified trusted-fixture receipt is
not hostile-code, tenant isolation, frontend-executor or production certification.

## Replica boundary and verification

This release is **not independent-replica readiness**. Generic JSON RPCs and the
tenant admission ledger coordinate via Postgres; run leases/checkpoints,
private SQLite ceilings, uploads/artifact binaries and learner erasure/recovery
still need a single-writer/shared-disk deployment. The request gate refuses
`MAMMOTH_REPLICA_COUNT` values other than `1`; it does not discover undeclared
replicas. Do not autoscale the backend to independent disks yet.

CI's required `shared-postgres` job runs the real migrations in an isolated
PostgreSQL 16 database and tests SQL permissions, concurrent reservations,
unknown costs, settlement and completion wiring. Local equivalent:

```powershell
$env:PYTHONPATH="$PWD\src"
$env:MAMMOTH_TEST_POSTGRES_CONTAINER="your-dedicated-test-container"
$env:MAMMOTH_REQUIRE_POSTGRES_TESTS="1"
python -m pytest tests\test_shared_state_admission.py -q
```

The named container must be dedicated test infrastructure. Tests create/drop a
random database, never use production, and make no paid provider calls.
