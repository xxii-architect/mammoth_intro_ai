# Shared runtime operations

## What this release changes

Generic JSON collections (notes, tasks, approvals, activity, audit, feedback,
build log, sales, snapshots, generated-document ownership and eval history)
use a common read/modify/write store. Local saves are locked, atomic and fsynced.
Concurrent disjoint keyed records merge; competing edits are rejected, not
last-write-wins. An unkeyed collection cannot be safely merged and returns a
conflict. A 409 requires reloading and an explicit new decision, never blindly
retrying a side effect. Corrupt records produce 503 without resetting data.
Activity events use a separate atomic append-and-retain operation: local locking
or a fresh bounded CAS computation keeps the latest 250 entries without turning
normal retention contention into a failed workflow. Only the pure event append
is recomputed, never the action that produced it; ordinary edits retain conflicts.

Onboarding, notifications, execution events and account-deletion request records
also use this backend, not direct filesystem overwrites. Disjoint keyed updates
merge while competing record edits fail explicitly. Notifications retain the
latest 1,000 entries and execution events the latest 200 through atomic
append-and-retain; workflow actions are not replayed to retry these writes.
Corrupt/wrong-shaped records are errors, never silently replaced by empty data.
Account export reads the selected backend for these shared collections.
Learning exports also read linked notes from that backend, filtered to the
authenticated user and active learning account. A notes read failure rejects
the export instead of falling back to a potentially stale local file. These
exports are not transactional snapshots of notes and learner data.
On the local learner backend, model operations recheck the active account and
learning-erasure epoch under the state lock before accessing the model. Work
is rejected if its account changed (including a switch away and back) or
saved-learning deletion occurred. Learner approvals are also bound to these
epochs, so an old approval cannot authorize adaptation after either event.
Learner and session resets save their state and clear the draft under the state
lock, preventing a reset from recreating a draft after concurrent deletion.
If the state save succeeds but draft reset fails, the request reports possible
partial changes. A rejected or failed state save also reports that the earlier
private-model reset may already have happened; reload before an explicit retry.
Legacy unkeyed trust metrics also use the selected backend without changing
their payload shape. Their concurrent changes may conflict; telemetry failures
are explicitly logged and do not replay or fail an already-computed response.
Deletion requests remain the existing request/cancellation workflow, not proof
that provider records, backups or every stored copy have been erased.

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
are opt-in. The private login-wide ceiling remains additive, using SQLite by
default or the explicitly selected PostgreSQL backend described below.

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

## Shared run checkpoints and private login admission

Ordinary and recursive runs can now use PostgreSQL checkpoints and dedicated
session advisory leases. Distinct workers coordinate without a shared disk.
A dead worker releases its database-session lease; a worker that loses its
connection cannot silently reconnect and save a late checkpoint. Checkpoint
revisions reject stale writes. Cancellation survives process loss, is writable
from another worker and cannot be undone by an older checkpoint. Retention
does not delete active, approval-pending or currently leased runs.

The private login-wide token ledger also has an optional normalized PostgreSQL
backend. Admission, settlement and limit changes serialize per owner.
Unknown outcomes retain reservations; larger reported totals remain visible.
Its public usage/observed-provider-health contract is unchanged. This does not
add invoice reconciliation or extend paid-path coverage.

### Reviewed migration and rollback

These settings do not migrate existing data. Stop writers and back up the
private directory/database before activation. Do not select an empty backend.

1. Apply `supabase_agent_runs.sql` and `supabase_private_admission.sql` through
   the trusted database administration path. Both are additive, service-only
   tables, with anonymous/authenticated SQL access denied.
2. Set `MAMMOTH_POSTGRES_DSN` privately on the backend, a deployment-specific
   `MAMMOTH_STATE_NAMESPACE`, and `MAMMOTH_POSTGRES_SESSION_MODE=direct`.
   **Direct or session-mode pooling only: never transaction pooling.**
   Install the declared `postgres` package extra (included in server requirements).
3. Inventory each actual user's hashed storage key and its associated owner
   through trusted administration. There is deliberately no reverse ownership
   guess from a directory name. For every reviewed owner, create a private
   runtime backup from their existing run directory and SQLite usage file:

   ```powershell
   python scripts\migrate_runtime_storage.py local-export --user-id REVIEWED_OWNER --runs-dir C:\private\REVIEWED_RUN_FOLDER --ledger-file C:\private\REVIEWED_USAGE.sqlite3 --file C:\private\runtime-backup.json --confirm-quiesced
   python scripts\migrate_runtime_storage.py import --user-id REVIEWED_OWNER --file C:\private\runtime-backup.json --confirm-quiesced
   ```

   Both local paths must exist; missing state is not assumed to be empty.
   The all-or-nothing per-owner import refuses any existing destination state.
   It preserves run revisions, approval/workflow evidence, cancellation,
   limits and all historical/pending/unknown reservations.
4. Export the imported owner into a new private file and compare the payload:

   ```powershell
   python scripts\migrate_runtime_storage.py export --user-id REVIEWED_OWNER --file C:\private\runtime-verified.json --confirm-quiesced
   ```

5. Only after every ownership/import check passes, select
   `MAMMOTH_RUN_BACKEND=postgres` and `MAMMOTH_PRIVATE_USAGE_BACKEND=postgres`,
   then restart through the approved deployment process and smoke-test before
   reopening writes. Either switch can be deferred independently. Database
   failure is explicit; there is no success-shaped local fallback.
6. To roll back after shared writes, stop writers again and export the **latest**
   database snapshot. Restore to new private paths:

   ```powershell
   python scripts\migrate_runtime_storage.py restore-local --user-id REVIEWED_OWNER --file C:\private\runtime-latest.json --runs-dir C:\private\restored-runs --ledger-file C:\private\restored-usage.sqlite3 --confirm-quiesced
   ```

   Outputs must not exist. Verify the restored files, retain both backups,
   then install them into the reviewed owner's original private paths through
   normal backup/restore procedures before selecting `local`. A failed restore
   is not usable state. Never switch onto stale originals.

For read-only production discovery, dispatch **Owner Container Acceptance**
with `target=storage-preflight`. It uses pinned SSH and the live service UID/
checkout, emits only credential-presence booleans and allowlisted backend
labels, and never deploys, connects to the database, migrates or restarts.
Presence of a DSN does not prove database connectivity, privileges or schema
readiness. Without an authorized database administration/session connection,
production migration is blocked; do not improvise a replacement database.

## Shared learning request controls

`MAMMOTH_LEARNING_CONTROLS_BACKEND=postgres` additionally replaces the private
per-login learning-controls SQLite database, after applying the service-only
`supabase_learning_controls.sql`. It uses the same private DSN and deployment
namespace. Default is `local`; invalid settings/database errors never fall back.

Request-count ceilings serialize per owner across workers. Cancellation is
shared across worker/thread safe boundaries, including account-specific
cancellation; it does not cancel an already-sent provider call or refund the
admission. Unknown/running operations remain retained without automatic replay.
The latest 100 finished operations are retained alongside **all** unfinished
operations. The public `mammoth.learning-controls.v1` payload is unchanged.
These counts are still admitted HTTP requests, not tokens or dollars.

Include each reviewed owner's existing controls database in the quiesced runtime
backup using `--learning-controls-file C:\private\REVIEWED_CONTROLS.sqlite3`.
The same import transaction then preserves its limit, daily admission counts,
operation/account ownership, completion evidence and pending cancellations.
Export includes controls when present. For rollback, add
`--learning-controls-file C:\private\restored-controls.sqlite3` to `restore-local`;
it must be a new output path. A backup containing controls cannot be restored
without this explicit path, and an absent controls backup cannot create an empty
policy. Runtime backup v1 cannot represent shared learner operation fences;
its PostgreSQL export refuses owners with retained fences instead of silently
discarding them, and import/restore refuse unsupported control fields. The
experimental learner/control backup captures fences but does not capture runs
or runtime usage, so it is not a replacement for a complete runtime backup.
The runtime importer and exporter also coordinate with the learner migration
lock for controls. They still require all writers to be stopped, including
runtime writers that do not use that lock. Apply all documented schemas before
running the combined exporter.
Verify the restored payload before selecting local storage again.

This removes one local-disk component, **not** the learner state/draft/model
erasure and recovery transaction boundary. Their filesystem locks remain
required, so this setting does not authorize independent replicas.

## Shared documents, indexed sections and review checkpoints

`MAMMOTH_DOCUMENT_BACKEND=postgres` replaces document-library SQLite metadata,
raw uploaded binaries, extracted-section JSON and saved indexed-review state
**together**, after applying `supabase_documents.sql`. It uses the same private
DSN and deployment namespace. Every query is owner/namespace-scoped; service-only
SQL permissions and foreign keys enforce document/review identity and cascading
deletion. Nothing is exposed through browser database credentials.

Uploads still stream into bounded private temporary parser input, with the
existing extension, size, extraction and processing-slot limits. Successful
ingestion commits raw bytes, metadata and sections atomically; parser failure
does not consume durable quota. Temporary input is removed before the request
returns. Cross-worker file/byte quotas serialize per owner. The default 50 MiB
file and 500 MiB per-owner raw-storage bounds remain unchanged. Indexed-section
and review API payloads remain unchanged; no filesystem paths are returned.

The initial durable binary store is PostgreSQL `bytea`, not an object-storage
bucket or a claim of unlimited binary scale. It avoids partial cross-system
commits and additional bucket credentials for the existing bounded library.
Database backups/storage capacity now include uploaded bytes and indexed text;
operators must provision/monitor that cost and capacity before activation.
This option does not move generated-artifact binaries or host repositories.

Saved-review quota/create and advance/synthesis claims are transactional.
Unknown/inflight model work stays blocked after restart, never replayed.
Budget changes retain their expected-ceiling check and audit history. Deleting
a document removes its bytes, sections and reviews in one transaction; a late
review save cannot resurrect them.

### Document migration and rollback

Stop **all** upload/review writers and back up the source/database. For every
explicitly reviewed owner, use real source directories (no ownership guessing):

```powershell
python scripts\migrate_document_storage.py local-export --user-id REVIEWED_OWNER --local-dir C:\private\REVIEWED_LIBRARY --legacy-chat-dir C:\private\REVIEWED_CHAT --legacy-atlas-dir C:\private\REVIEWED_ATLAS --backup-dir C:\private\document-backup --confirm-quiesced
python scripts\migrate_document_storage.py import --user-id REVIEWED_OWNER --backup-dir C:\private\document-backup --confirm-quiesced
python scripts\migrate_document_storage.py export --user-id REVIEWED_OWNER --backup-dir C:\private\document-verified --confirm-quiesced
```

Backup outputs must be new directories. Each contains per-file metadata/index/
review JSON, raw binary and SHA-256, with the owner manifest written **last**.
A missing manifest, changed checksum, missing original binary, invalid owner,
duplicate review or exceeded configured quota blocks import rather than
discarding content. Resolve source corruption before migration. Private
backups contain original user content; keep them out of source control/artifacts.
The per-owner import is all-or-nothing and refuses existing documents. Compare
both backups, including hashes and pending-review markers, before selecting
`MAMMOTH_DOCUMENT_BACKEND=postgres` through the approved deployment procedure.

For rollback, stop writers again, export the latest shared state into a new
backup directory and restore into a **new** private library:

```powershell
python scripts\migrate_document_storage.py restore-local --user-id REVIEWED_OWNER --backup-dir C:\private\document-latest --local-dir C:\private\restored-library --confirm-quiesced
```

Only a completed restore has `restore-complete.json`. Verify its re-export
against the latest backup before installing it into the reviewed owner's
original location and selecting `local`. A failed partial restore must never
be activated; existing output directories are never overwritten.

## Shared generated research documents (optional)

`MAMMOTH_GENERATED_ARTIFACT_BACKEND=postgres` stores generated DOCX ownership and
bytes together in private PostgreSQL tables. `local` remains the default.
Apply `.mammoth\supabase_generated_artifacts.sql` through the reviewed SQL
administration channel first. Configure the private `MAMMOTH_POSTGRES_DSN` and
explicit `MAMMOTH_STATE_NAMESPACE`; never put connection values in chat, source,
backup manifests or browser configuration. Invalid/unavailable storage does
not fall back to local downloads.

The generator still writes a private staging file. Publication commits the
bytes before removing that file; downloads on another worker use the database,
not the generator's disk. Staging cleanup failures are logged separately.
Document publication runs before workspace archival. A failed publication keeps
the draft text but removes the download filename and records
`quality.generated_document.status: "failed"` with a stable error code. It does
not replay paid work.

Limits are 50 MiB per file, 2 GiB and 2,000 files per owner. Quotas serialize
across workers; reaching them fails publication without pruning older files.
Identical owner/name/content registration is idempotent. A filename cannot be
overwritten or claimed by another owner, even by an administrator. Downloads
retain signed-in, owner-or-admin access and identical missing/not-owner 404s.
Imported documents without ownership remain admin-only, never auto-assigned.
SQL access is service-only with RLS; browser roles cannot read the tables.
Database backups/capacity must include these `bytea` binaries.

### Generated-document migration and rollback

This is a **namespace-wide** backup containing private documents from multiple
users, including admin-only legacy files. Stop all generator, ownership,
download and other writers during the reviewed cutover. Review the explicit
source directory and authoritative ownership snapshot; do not infer ownership
from filenames. If ownership currently uses shared JSON, first export that
record through the existing shared-state backup procedure; a stale local index
is not an authoritative snapshot.

```powershell
python scripts\migrate_generated_artifacts.py local-export --namespace REVIEWED_NAMESPACE --generated-dir C:\private\generated_docs --owners-file C:\private\generated_doc_owners.json --backup C:\private\generated-before --confirm-quiesced
python scripts\migrate_generated_artifacts.py import --namespace REVIEWED_NAMESPACE --backup C:\private\generated-before --confirm-quiesced
python scripts\migrate_generated_artifacts.py export --namespace REVIEWED_NAMESPACE --backup C:\private\generated-after --confirm-quiesced
```

Outputs must be new private directories. The `mammoth.generated-artifacts-backup.v1`
manifest is written last and records names, owners (or null for admin-only),
sizes and SHA-256 checksums, never credentials. Import validates every binary
and ownership record in a single transaction, refuses nonempty destinations,
and rolls back earlier inserts if any later record fails. Compare the
re-exported manifest and binaries before selecting the PostgreSQL backend.
Backup directories require the same protection as the originals.

For rollback, stop writers, export the latest shared state into a new backup
and restore into a **new** private directory:

```powershell
python scripts\migrate_generated_artifacts.py restore-local --namespace REVIEWED_NAMESPACE --backup C:\private\generated-latest --restore-dir C:\private\generated-restored --confirm-quiesced
```

Only a completed restore has `restore-complete.json`. Verify its re-export
before installing `generated_docs` and `generated_doc_owners.json` into the
reviewed local locations and selecting `local`. Do not activate a partial
restore or merge a rollback into existing files. Missing original binaries or
owner references block migration instead of silently omitting data.

## Shared chat threads (optional)

`MAMMOTH_CHAT_BACKEND=postgres` stores thread metadata and up to 120 messages
together under exact namespace/user/thread identities. Apply
`.mammoth\supabase_chat_threads.sql` first; use the existing private
`MAMMOTH_POSTGRES_DSN` and explicit `MAMMOTH_STATE_NAMESPACE`. `local` remains
the default; invalid/unavailable configuration never falls back to disk.
Legacy local ownership paths still use lossy normalization: do not infer an
owner from their directory names or silently activate shared storage over them.

Thread operations serialize per owner. The active limit is 200 threads; create
fails at the limit rather than silently pruning conversations. Each combined
metadata/message record is limited to 4 MiB of ASCII-escaped JSON. Metadata and
messages commit together. Whole-history replacement checks its pre-generation
revision; run exchanges are keyed by run ID and merge without duplicating
prompts. Renames survive run-exchange writes.

Deletion clears metadata/messages but retains a minimal identity/revision
tombstone. Missing/deleted thread IDs cannot be auto-created by a late model
completion, continuation or restored request. These fences are not message
content, are retained without automatic expiry, and must be included in backup
and rollback capacity planning. This is not a full account-erasure certificate.
Stream completion payloads add `thread_save` (legacy chat) or `chat_save`
(agent-run terminal event) so a generated response can explicitly report a
failed save without replaying paid work. Existing event fields are unchanged.
Global learner-backed chat history still requires its separate migration.

### Chat migration and rollback

Stop chat/run/continuation/deletion writers. Explicitly review the legacy
directory and owner: normalization collisions, unindexed messages or missing
message files block export rather than silently assigning or omitting data.
Supply `--confirm-legacy-owner` only after that review:

```powershell
python scripts\migrate_chat_threads.py local-export --user-id REVIEWED_OWNER --local-dir C:\private\reviewed-chat-owner --backup C:\private\chat-before --confirm-quiesced --confirm-legacy-owner
python scripts\migrate_chat_threads.py import --user-id REVIEWED_OWNER --namespace REVIEWED_NAMESPACE --backup C:\private\chat-before --confirm-quiesced
python scripts\migrate_chat_threads.py export --user-id REVIEWED_OWNER --namespace REVIEWED_NAMESPACE --backup C:\private\chat-after --confirm-quiesced
```

Backups use `mammoth.chat-threads-backup.v1`, a SHA-256 checksum, explicit owner,
revisions and deletion fences; the manifest is written last. Import validates
the full backup before its single transaction and refuses existing records or
fences. Verify re-exported metadata, messages and identities before selecting
the PostgreSQL backend. Local imports assign revision 1; shared re-exports
preserve subsequent revisions.

For rollback, stop writers, export the latest shared state and restore to a new
directory:

```powershell
python scripts\migrate_chat_threads.py restore-local --user-id REVIEWED_OWNER --backup C:\private\chat-latest --local-dir C:\private\chat-restored --confirm-quiesced
```

Only a completed restore has `restore-complete.json`. Verify its re-export
before installing it into the explicitly reviewed legacy owner directory and
selecting `local`. The local reader honors restored `_deleted.json` fences.
Rollback refuses identities that would collide under legacy filename
normalization. Do not activate partial restores or discard fences to bypass a
conflict. Backups contain private conversation content; protect them accordingly.

## Replica boundary and verification

Local learner-state saves also check the account-switch epoch under the state
lock. A delayed request cannot restore an older account or session after a
switch, including switching away and back; it must reload instead.
Local account creation, deletion and switching also compare the complete
saved-state snapshot under that lock before writing. A concurrent change
returns a conflict instead of overwriting it. Each successful account
transition advances a separate account-collections epoch so delayed local
state or adaptation writes cannot undo an inactive-account change. This is
local-file concurrency protection, not the shared PostgreSQL integration.
Account creation also rejects an ID with an unassigned saved session rather
than overwriting it; review that session before resolving the conflict.
Unknown per-account session fields are retained across normal saves and
account switches; they are not promoted into the active session response.
Unknown state and session extensions remain outside both saved-learning and
adaptation deletion scopes; the deletion previews disclose this exclusion.
Workspace request exercise keys also bind the account-switch epoch, while
stored draft identity stays compatible with existing records. Switching away
and back preserves the saved draft but rejects a delayed write from before the
switch. Ordinary draft saves preserve unrecognized top-level record fields
instead of silently discarding them.

An experimental PostgreSQL learner-bundle primitive and schema exist for
testing only. They are **not a runtime backend**, do not read existing learner
files and must not be used to activate or migrate production learner data.
They provide exact-owner whole-bundle revision checks and a namespace
migration lock. A separate experimental transaction API tests revision-bound
draft reads, saves and revision-checked clearing; allowlisted active-account
learning-session updates requiring a live tracked operation; adaptation writes;
coordinated request admission; and atomic
account-scoped learning/adaptation deletion with cancellation in PostgreSQL.
An experimental result operation also commits the updated private model,
learning-session fields and adaptation caches together, using the same model
calculation as local learner updates. It requires a revision and a live,
epoch-fenced operation; cancellation or deletion prevents stale publication.
An experimental onboarding operation similarly updates the model and caches
in one transaction. Its guard binds the owner, namespace, account and
account/deletion epochs; switching away and back or erasure invalidates an
old approval even if the caller supplies the latest revision. This guard and
operation are not yet connected to the live approval or onboarding routes.
The guard is a concurrency fence, not an authorization credential; live
integration must still validate authenticated ownership and approval state.
An experimental learner/session reset atomically clears progress and the
active recovery draft, refreshes the state caches, and cancels tracked
account work. A reset epoch fences both older operations and approvals;
onboarding and other retained model fields are not erased. The reset is not
wired into live routes and is not a deletion receipt.
Coordinated admission binds each operation to the current account-switch,
account-collections, learning-erasure, adaptation-erasure and reset epochs in the same transaction. An
unbound or stale operation cannot write a session or model even when presented
with a newer bundle revision. Fences follow operation retention.
It also tests active-account model reads that reject pending erasure and
content-free adaptation and learning deletion previews with exact typed
confirmation. Preview tokens bind the owner, namespace, account, deletion
scope, revision and complete bundle; a changed bundle invalidates the preview.
They are concurrency guards, not authentication or authorization. Unknown
model extensions block adaptation deletion until reviewed.
These operations are not wired into the live API; raw bundle reads and writes
remain available to migration/testing code and do not enforce those rules.
The session update surface covers only learning fields and cannot yet replace
the full live state writer. Generic learning-control admissions
do not carry learner fences and cannot write through these methods.
Experimental account creation, deletion and switching use the same owner
transaction and advance the epoch on active-account changes. They cancel
departing or deleted accounts' tracked operations atomically and preserve
separately stored models and drafts on account deletion, as the existing
account endpoint does. Recreating the same account identifier can therefore
make retained data accessible again; account deletion is not learner-data
erasure. Unassigned saved sessions block creation pending review. Legacy-state
normalization, full state updates and live route integration remain incomplete;
these methods must not be enabled alone.
Workspace artifact and run-history routes now use an internal storage seam.
The default remains the existing local state implementation; an unselected
PostgreSQL adapter is exercised only through test injection, including separate
worker processes and completed-run artifact archiving. Its scoped
collection writes check owner, active account, revision and epoch fence, and
preserve unrelated bundle data. This is not a backend selector and must not be
enabled independently of the remaining learner surfaces.
Saved curriculum library reads and writes also use this revision-checked,
owner/account-scoped collection seam when injected. Saved curriculum
activation also commits its first lesson, exercise, history, bounded telemetry
and recovery packet through the admitted, revision-fenced learner transaction.
These paths are exercised through test injection only; the local backend
remains the default, with platform-wide audit and real provider/sandbox
acceptance still open.
The tutor recovery-draft save route also has an unselected PostgreSQL adapter
tested through HTTP injection; it rejects stale revisions, account switches,
erasure and reset races without falling back to local files. Separate-process
tests also verify HTTP saves, stale writes and owner isolation; recovery reads
in those tests use the transaction API, not the status endpoint. Export and
reset are not part of this draft-save adapter.
The workspace account list and create/switch/delete routes have a separate
test-injected PostgreSQL adapter. Account transitions use a revision-checked
transaction and return the metadata view committed by that transaction;
account/session extension fields are not exposed in that view. Tests cover
separate processes, owner isolation, stale transitions, unavailable storage,
and unassigned sessions. Profile, tier and developer-access updates also have
test-injected transactions; each update and its bounded
`account_metadata_audit` entry commit atomically in the owner bundle. This is
not yet the platform-wide audit stream, and account lifecycle audit events
still use their existing separate surface. Legacy account normalization and
other learner routes remain outside this adapter. It is not a production
backend selector and must not be enabled alone.
Controlled-learning admission has a further test-injected seam that requires
owner-matched PostgreSQL controls and creates the operation fence in the same
transaction as the quota admission. HTTP rehearsals cover stale accounts,
limits, cancellation, completion and unavailable or mismatched controls.
Handler state and model writes still use local paths; this admission seam must
not be activated without the rest of the learner integration.
The tutor status snapshot and learner, lecture, module and library read routes
have a test-injected reader. It returns active-account session fields, the
validated learner model and recovery draft from one owner-scoped transaction;
it never hydrates or writes from the local learner files. Host-local evaluation,
sandbox and activity files are omitted from this shared status response. This
is read-path coverage only. Learning-history and private-adaptation
preview/confirmation routes use revision-bound transaction methods in tests.
Unapproved onboarding updates and progress-only learner resets now use
revision- and approval-fence-bound transactions in the same test-injected mode;
reset preserves onboarding while clearing progress and replacing the recovery
draft. Onboarding and learner/session reset approvals are stored and applied
transactionally in the owner bundle with a bounded audit log; other approval
operations are not enabled. Shared export requires
the shared notes backend. Lesson generation and submission/result persistence
are also test-injected routes when PostgreSQL controls are selected: generation
stores the curriculum/exercise/history under its admitted operation, and
submission commits the result, bounded lesson telemetry, adaptation and caches
in one fenced transaction. Unapproved session reset also uses that transaction
and clears bounded lesson telemetry; its approval path is blocked. Next/back
lesson navigation commits through the same revision- and operation-fenced
session transaction. Mastery overrides fail closed until the platform-wide
audit lifecycle is shared. Remediation regeneration and other tutor mutations
remain unintegrated, so these adapters are not a shared-backend selector.
Provider/sandbox execution has not been validated against production services;
route tests use deterministic fakes.
Shared reader mode also has an HTTP guard: any tutor route outside the explicit
test-covered read, draft-save, onboarding, progress-reset, deletion, lesson
generation/submission, and next/back navigation allowlist returns
`503 storage_unavailable` rather than reading or writing local learner files.
Manual and requested failed-submission remediation regeneration are covered.
Remediation uses a second fenced commit after the result transaction; if that
second step fails, the result remains committed and clients must reload rather
than replay the submission. Mastery overrides remain outside the allowlist
until their audit lifecycle is shared.
Account profile and entitlement routes are available only when both the
test-injected account adapter and learner reader are installed; billing-usage
routes remain blocked until their authoritative state and audit behavior are
integrated. The shared learner approval list, approval and deletion routes are
owner-scoped in the learner bundle. Only onboarding and learner/session reset
approvals are supported; each request, application and deletion is audited in
the same transaction as its state change. Stale account/fence checks reject
execution, and retries of an already approved record do not replay the action.
The signed-in owner can review their own records; a different user cannot see,
approve or delete them. Other approval types and generic local approval
creation/execution are blocked in shared mode; platform-wide audit integration
remains outstanding.
Operation admission itself is tested against the shared transaction API.
Lesson generation and submission can run only with explicitly selected shared
controls and the test-injected learner adapter; provider/sandbox behavior,
retry outcomes and production acceptance are still unverified.
When the explicit PostgreSQL learning-controls backend is selected alongside
the test-injected learner reader, controls reads/limit updates and owner-scoped
cancellation use PostgreSQL without touching local learner files. The
unselected/default mode still blocks these routes rather than falling back.
This does not enable any production backend or replica configuration.
The experimental API does not provide complete runtime coverage, end-to-end
migration, whole-platform deletion receipts or activated rollback. Raw
bundle methods must never be wired directly to a user-facing endpoint; use
the confirmed methods only after all runtime and migration gates are satisfied.
Those domain guarantees and an end-to-end migration must be implemented and
tested before any activation decision. The SQL file is not an instruction to
apply that schema to production.

An experimental offline source-backup tool is available for reviewed fixtures,
not production activation. It requires all writers to be stopped and an exact
owner and state file to be supplied. The operator must independently verify
ownership: legacy owner filenames normalize identifiers and can collide.
The tool discovers drafts for known accounts, rejects unidentified draft files,
and accepts `--account-id` for independently identified removed accounts.
Orphan model directories cannot be attributed from their hashes alone; the
operator must inventory them and explicitly supply any missing account IDs.
The backup preserves pending erasure records and unknown JSON model fields;
unknown model files block backup. It does not include unrelated curricula,
controls, notes, uploads, provider records or backups.

For a quiesced fixture, the optional `inventory` command checks a separately
reviewed owner/account mapping against one learner-state directory. A private
JSON file has exactly this shape (the identifiers here are examples):

```json
{"owners": {"reviewed-owner": ["removed-account"]}, "reviewed_curricula": []}
```

```powershell
python scripts\backup_learner_source.py inventory --state-dir C:\private\atlas_state --inventory-file C:\private\reviewed-owners.json --confirm-quiesced
```

The review rejects normalized owner collisions, missing owner state files,
unmatched state/draft/model files and controls WAL files. Every existing
curriculum filename in that directory must be classified explicitly in
`reviewed_curricula`; names alone do not prove a file is not another owner's
state. The operator must independently establish ownership and supply removed
account IDs, including accounts no longer in saved state. Matching hashes or
names cannot prove those assertions, and files outside the selected directory,
controls contents and external sources are not inventoried. This command does
not produce a backup or authorize migration or activation.

For a private, access-restricted fixture directory (set `PYTHONPATH=src`):

```powershell
python scripts\backup_learner_source.py backup --user-id REVIEWED_OWNER --state-file C:\private\atlas_state_REVIEWED_OWNER.json --backup C:\private\learner-backup --confirm-quiesced
python scripts\backup_learner_source.py verify --user-id REVIEWED_OWNER --backup C:\private\learner-backup
python scripts\backup_learner_source.py restore-fresh --user-id REVIEWED_OWNER --backup C:\private\learner-backup --restore-dir C:\private\learner-restore
```

Use the actual normalized legacy filename, not the example placeholder. Supply
additional reviewed accounts with repeated `--account-id` options. Verification
checks the checksum and record shapes, not ownership, completeness or
authenticity. Keep the backup private and configure filesystem ACLs explicitly
on Windows; the checksum is not a signature. A missing manifest means the
backup did not complete. The restore requires a new directory and re-reads
all restored records before writing `restore-complete.json`; a missing marker
means the restore is partial and must not be used. This restores only records
in the backup and does not resolve its ownership or completeness limitations.
There is an experimental `python -m scripts.migrate_learner_bundle` import/export
rehearsal for **isolated test databases only**, requiring explicit test-only and
quiescence confirmations. Import refuses an existing owner row, and export
refuses missing or invalid records. The database bundle does not retain a
backup's list of reviewed accounts that have no records: an operator must
provide those again with `--account-id` on export. These commands do not
establish source ownership, migrate controls, enforce erasure or coordinate
running learners. Never use them for production migration or activate this
bundle as a learner backend.

An additional test-only Python rehearsal, `import_with_controls_rehearsal`,
imports a validated learner backup and the learning-controls portion of a
reviewed runtime snapshot in one PostgreSQL transaction. It rejects missing
controls, unknown controls fields, unfinished operations and any preexisting learner or control rows;
a failure rolls back both. The runtime snapshot's other data is not imported.
The namespace lock coordinates learner-bundle transactions and the current
generic PostgreSQL learning-controls API. **All** learner and controls writers
must still be stopped, including older deployments and direct database writers
that may not honor the lock.
The separate inputs do not prove ownership, integrity of the runtime snapshot,
completeness, simultaneous capture, or readiness for rollback or production.
There is no production CLI or activation path for this rehearsal.
The test-only `import_reviewed_batch_rehearsal` validates each reviewed owner
before importing all owners and their controls in one transaction. Duplicate
owners, an occupied destination or a failure on any owner abort the entire
batch. It shares the same quiescence, ownership, snapshot and production
limitations as the single-owner rehearsal, and does not import runs or runtime
token usage. It rejects owners that collide under legacy filename normalization.
`import_full_batch_rehearsal` additionally imports reviewed runs and token
usage in the same transaction, including unresolved reservations; preserving
them does not resolve or authorize replay of unfinished work.
Companion `export_with_controls_rehearsal` and `import_combined_rehearsal`
functions exercise a repeatable-read database snapshot and fresh-namespace
restore. The export acquires the exclusive session advisory lock before
establishing its database snapshot, so a learner writer that committed while
the export waited is included. This requires a direct or session-mode
connection, not transaction pooling. The v2 rehearsal includes retained
operation fences, including unknown fence extensions, in the checksummed
controls portion. Restores reject missing fences, duplicate or unmatched
operation references, and older v1 combined backups. Local-source controls
do not have shared operation fences. The export writes a completion marker last, binding checksums for
both portions; a missing marker or changed payload blocks import. Checksums
are not signatures. Controls and learner writers must still be quiesced:
older processes or direct database writers may bypass the lock, and the
snapshot is not proof that external work has stopped or that production
rollback is safe. Reviewed accounts with no records must still be supplied
explicitly when exporting.

`export_full_rehearsal` and `import_full_rehearsal` exercise a single-owner,
fresh-namespace restore of learner bundles, controls and operation fences,
agent runs, and token-usage policy and attempts. The export obtains the
learner namespace session lock before its repeatable-read snapshot and writes
a completion marker binding the learner manifest and all payload checksums.
Restore rejects corrupt or incomplete backups and rolls back all inserts if
any destination is occupied. These are isolated-test Python functions, not a
production migration or rollback procedure. All writers must stop: the learner
lock does not exclude runtime-run or token-usage writers. Quiescence, ownership,
external sources, authentication, backup integrity against a malicious actor,
and data outside these tables remain independently unverified. Checksums are
not signatures and a successful rehearsal does not authorize activation.
The test-only namespace variants, `export_full_namespace_rehearsal` and
`import_full_namespace_rehearsal`, inventory the covered tables against an
explicit owner/account list, capture all reviewed owners in one snapshot, and
restore them together only into an empty covered namespace. They reject
unreviewed table owners, missing or modified owner payloads, and occupied
destinations. An operator must still review owners and retained account IDs;
the database inventory cannot find data outside these tables or prove that
writers have stopped. The same non-production and no-activation restrictions
apply.

This release is **not independent-replica readiness**. Generic JSON RPCs and the
tenant admission ledger coordinate via Postgres, with new optional PostgreSQL
run leases/checkpoints, private login ceilings, learning controls and document
libraries, plus optional generated-document ownership/bytes and chat threads.
Unmigrated global chat history, host-side stores and learner erasure/recovery still need a
single-writer/shared-disk deployment. The request gate refuses
`MAMMOTH_REPLICA_COUNT` values other than `1`; it does not discover undeclared
replicas. Do not autoscale the backend to independent disks yet.

CI's required `shared-postgres` job runs the real migrations in an isolated
PostgreSQL 16 database and tests SQL permissions, concurrent reservations,
unknown costs, settlement and completion wiring. Local equivalent:

```powershell
$env:PYTHONPATH="$PWD\src"
$env:MAMMOTH_TEST_POSTGRES_CONTAINER="your-dedicated-test-container"
$env:MAMMOTH_REQUIRE_POSTGRES_TESTS="1"
python -m pytest tests\test_shared_state_admission.py tests\test_postgres_run_store.py tests\test_postgres_documents.py tests\test_generated_artifacts.py tests\test_postgres_chat_threads.py -q
```

The named container must be dedicated test infrastructure. Tests create/drop a
random database, never use production, and make no paid provider calls.

### Shared learner activation gate

The shared learner adapter remains test-injected; no production backend selector
or activation procedure is approved. Keep `MAMMOTH_STATE_BACKEND` unchanged and
`MAMMOTH_REPLICA_COUNT=1` until every gate below is evidenced in staging:

1. **Runtime completeness:** migrate every learner/tutor write and read, account
   lifecycle, approval/claim/execute/delete, audit, usage, export, erasure and
   recovery path to owner-scoped transactions. Unsupported operations must keep
   returning `503` without local fallback.
2. **Real execution:** validate provider, sandbox, timeout, cancellation,
   partial-failure and retry behavior with approved staging credentials. Confirm
   a committed submission is never replayed after a later response failure.
3. **Source review and quiescence:** identify every legacy owner/account and
   state source, reconcile unknown/orphaned records, and stop all web workers,
   background workers and direct writers. Confirm no learning operation remains
   unresolved. The advisory migration lock alone does not establish quiescence.
4. **Complete backup and restore:** create a restricted, independently verified
   backup that covers all affected runtime data and external sources, not only
   learner bundles. Verify checksums and ownership, restore into a fresh staging
   namespace, and compare reviewed record counts and content without exposing
   learner data in logs.
5. **Rollback exercise:** rehearse stopping all writers, capturing writes made
   since migration, restoring or reverting every affected data surface, and
   verifying service behavior and owner isolation. A fresh-database import test
   is not rollback evidence.
6. **Staging acceptance:** test owner isolation, account switching, stale-write
   rejection, deletion, approvals/audit, usage, provider/sandbox execution,
   service restart and recovery. Record pass/fail evidence and the exact code,
   schema and configuration revisions.
7. **Production go/no-go:** verify the production DSN/namespace, TLS, service
   permissions, backup location, replica count and rollback operator out of
   band. Require explicit operator approval and a maintenance window before
   applying schema, changing configuration or restarting production.

Any failed, missing or ambiguous gate is a no-go: leave shared storage disabled,
keep the single-writer configuration, and do not apply the learner schema to
production. The local PostgreSQL tests and current rehearsal scripts close only
code-level/test-fixture checks; they do not satisfy these deployment gates.
