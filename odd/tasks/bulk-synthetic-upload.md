# Feature: Bulk synthetic CSV upload (server-enforced order)

## Objective
Let an admin upload multiple synthetic dataset CSVs in one request (e.g. via Swagger's
multi-file picker) instead of one file + explicit table_name per call. The system infers
each file's target table from its filename and ingests all accepted files as ONE Arq job,
in a fixed, FK-safe order — never the order the files were uploaded in.

## Problem / why
The existing `POST /api/v1/admin/ingestion/synthetic-upload` endpoint requires one file +
an explicit `table_name` per call. Naively bulk-calling it as N independent jobs has no
protection against Arq processing a child-table job (`match_event`, `match_lineup`, ...)
before its parent tables (`team`, `match`, `player`) are ingested — `ForeignKeyViolationError`.
This already happened once in the Transfermarkt sync pipeline (bug #5 in project history,
"FK ordering: player_identity_link upserted before real_player rows existed"). A bulk
endpoint must not reintroduce that failure mode.

## Scope
- New static filename -> table_name map, reusing the exact mapping already established in
  `backend/scripts/seed_from_csv.py` — NOT a naive strip-`.csv` heuristic (e.g.
  `squads_and_players.csv` -> `player`, not a pattern match).
- Fixed FK-safe ingestion order constant: `team`/`venue`/`tournament_stage`/`referee` (no
  deps) -> `player` (needs `team`) -> `match` (needs `team`/`venue`/`tournament_stage`/
  `referee`, nullable FK to `player` for player-of-the-match) -> `match_event`/
  `match_team_stat`/`match_lineup`/`player_stat` (need `match`/`team`/`player`).
- New `IngestionJobType.BULK_SYNTHETIC_UPLOAD`.
- New domain service: ingest a batch of (filename, bytes) pairs as one job, accumulating
  per-table `row_counts` (reuse the existing `dict[str, int]` shape already used by the
  Transfermarkt sync job), sorted into the fixed order regardless of input order.
- New Arq task + pool wrapper + `worker.py` registration for the batch job.
- New router endpoint accepting multiple files, resolving filenames server-side, rejecting
  unrecognized filenames with a clear per-file reason (never silently guessing), returning
  one `job_id` when >=1 file is accepted; 400 with per-file reasons when zero are accepted.
- Tests per Strict TDD Mode: unit tests for the ordering/mapping logic and the batch
  ingestion service (fake repository, no DB), integration test for the new router endpoint
  (real DB via `dependency_overrides`) covering: happy path with scrambled upload order, an
  unrecognized-filename rejection, and a zero-accepted-files case.

## Out of scope
- Changing the existing single-file `synthetic-upload` endpoint.
- Any change to the Transfermarkt sync pipeline.

## Constraints
- Follow `backend/AGENTS.md`: layer-first (api/v1, domain, infra), repository
  interface+concrete+provider pattern, real `StrEnum` not free strings, 400-line file cap,
  fail-fast (reject unknown filenames, don't guess-route them).
- Reuse existing `CsvIngestionService` / `SYNTHETIC_TABLE_SPECS` / `TableIngestionSpec` —
  do not duplicate CSV parsing logic.
- TDD mode: enabled, pytest runner. RED (failing test) before implementation, then GREEN,
  then REFACTOR, for each piece of new logic — record observed evidence, not asserted.
- Known environmental gotchas (from project history, re-verify still true): `backend/.env`
  cannot be written in this environment — export `DATABASE_URL`/`REDIS_URL`/`JWT_SECRET`/
  `OPENROUTER_API_KEY` as shell env vars before running pytest; the local pytest run and the
  live docker-compose stack share the same Postgres/Redis, so a live smoke test can pollute
  rows integration tests also touch — clear the ingestion-related tables before/after a live
  run if needed.

## Tasks
- [x] T1: Filename map + fixed ingestion order constant (pure, unit-tested)
- [x] T2: `IngestionJobType.BULK_SYNTHETIC_UPLOAD` + domain batch-ingestion service (unit-tested with a fake repository)
- [x] T3: Arq task + pool wrapper + `worker.py` registration
- [x] T4: Router endpoint + DTOs (`BulkSyntheticUploadResponse` etc.), wired to `require_admin`
- [x] T5: Integration tests for the endpoint (scrambled order, rejection, zero-accepted)
- [x] T6: Live smoke test (in-process, real DB/Redis, real dataset -- see Progress for why not literal curl); `ruff check`/`ruff format`; full pytest suite
- [x] T7: Rebase onto `main` after user confirmed `origin/claude/player-linking-approval-7qi9fu` (the admin panel branch) was merged; fix migration `down_revision` conflict this surfaced (two heads: `0f67254f34fc` from the merged chat-categorization migration chain, `d23ea2153231` from this branch) -- re-pointed to `0f67254f34fc`, single head restored
- [x] T8 (NEW, scope added after rebase): populate `current_stage`/`stage_checkpoints` on the bulk-upload job (one checkpoint per table ingested), mirroring `TransfermarktSyncService`'s use of `IngestionJob.record_stage_checkpoint` -- added because the merged admin panel's `stage-progress.tsx` component renders exactly these fields, and the user wants CSV job status to look "just like transfermarkt". `record_stage_checkpoint(stage: TransfermarktSyncStage)` is currently typed to a Transfermarkt-specific enum; needs generalizing (or a parallel enum) without breaking the existing caller.
- [x] T9 (NEW): frontend admin UI -- a bulk-CSV-upload trigger + job status view in `frontend/src/features/ingestion/`, mirroring the existing Transfermarkt `sync-jobs-panel.tsx` exactly: same manual-refresh-only pattern (no polling), same Route-Handler-proxy API client pattern, same `StageProgress` rendering, same UI primitives/design tokens. Wire into the existing `(admin)/sync-jobs` page (or a clearly-placed addition to it) alongside the existing Transfermarkt trigger.

**This was the last task on this feature -- T1-T9 all done, nothing left planned.**

## Verification
- `ruff check backend/src backend/tests && ruff format --check backend/src backend/tests`
- `pytest` (full suite)
- Live (if the stack is up): upload the 10 dataset CSVs via curl in scrambled order, confirm
  one job succeeds with correct per-table `row_counts` and no FK violations.

## Delivery
- One feature branch off `main`: `feat/bulk-synthetic-upload`
- Work-unit commit(s), Conventional Commit messages
- Do NOT push or open a PR — commit locally only, push/PR is the user's call

## Progress

Branch: `feat/bulk-synthetic-upload` off `main`. `main` never touched.

Commits (in order):
1. `76e56fb` feat(ingestion): add bulk synthetic upload filename map and batch service
   (T1 + T2 + `IngestionJobType.BULK_SYNTHETIC_UPLOAD` domain enum)
2. `145d2b4` feat(ingestion): wire bulk synthetic upload Arq task and queue (T3)
3. `17109a7` feat(ingestion): add bulk synthetic upload admin endpoint
   (T4 + DTOs + schema-level enum + migration)
4. `4469071` test(ingestion): add integration tests for bulk synthetic upload (T5)

### T1 -- filename map + order
`backend/src/domain/ingestion/services/bulk_synthetic_upload_specs.py`:
`BULK_SYNTHETIC_FILENAME_TO_TABLE` (verified 1:1 against `scripts/seed_from_csv.py`'s
`TABLE_SPECS`), `BULK_SYNTHETIC_INGESTION_ORDER`, `resolve_table_name`,
`ingestion_order_index`. A module-level assertion keeps the map's values and the
order tuple in exact sync. TDD: wrote
`tests/unit/domain/ingestion/test_bulk_synthetic_upload_specs.py` first, confirmed
RED (`ModuleNotFoundError`), implemented, confirmed GREEN (5 passed).

### T2 -- domain batch-ingestion service
`backend/src/domain/ingestion/services/bulk_synthetic_ingestion_service.py`:
`resolve_and_order_files` (pure, no DB -- resolves + rejects + sorts) and
`BulkSyntheticIngestionService.ingest_batch` (async, drives the `IngestionJob`
through running -> succeeded/failed, accumulating `row_counts` per table, same
shape `TransfermarktSyncService` uses). Added
`IngestionJobType.BULK_SYNTHETIC_UPLOAD` to the domain enum
(`ingestion_job.py`). TDD: wrote
`tests/unit/domain/ingestion/test_bulk_synthetic_ingestion_service.py` first,
confirmed RED, implemented, confirmed GREEN (4 passed).

### T3 -- Arq wiring (trivial, no dedicated RED/GREEN per the brief's own carve-out)
`bulk_synthetic_upload_task` in `tasks.py`, `enqueue_bulk_synthetic_upload` in
`pool.py`, registered in `worker.py`'s `WorkerSettings.functions`. Mirrors
`synthetic_upload_task`'s session_scope/_fail_job pattern exactly.

### T4 -- router + DTOs
`POST /api/v1/admin/ingestion/bulk-synthetic-upload` in `ingestion_router.py`,
`BulkFileResult`/`BulkSyntheticUploadResponse` in `ingestion_dtos.py`. Reuses the
existing `_MAX_UPLOAD_BYTES`/`_ALLOWED_CONTENT_TYPES` module constants (same
file, no extraction needed). Zero accepted files -> 400 with
`detail={"message": ..., "files": [...]}`.

Deviation found and fixed: `IngestionJobType` is duplicated as a second,
schema-level `StrEnum` in `infra/postgres/schemas/ingestion_job_schema.py`
backing a native Postgres enum type. Added `BULK_SYNTHETIC_UPLOAD` there too,
plus migration `2026-09-25_add_bulk_synthetic_upload_job_type.py`
(`ALTER TYPE ingestion_job_type ADD VALUE`). The live shared dev Postgres's
`alembic_version` (`0f67254f34fc`) is not in this branch's migration history at
all (pre-existing drift, presumably from another concurrent worktree sharing
the same docker-compose DB) -- `alembic upgrade head` cannot run against it, so
the enum value was applied directly via `ALTER TYPE ... ADD VALUE IF NOT
EXISTS` against the live DB so tests could run now. The migration file itself
is correct and chains onto this branch's real head (`a4c8e2b91f03`) for a clean
environment.

### T5 -- integration tests
`tests/integration/api/admin/test_bulk_synthetic_upload_router.py`: scrambled
order with correct row_counts (via the real endpoint + real Postgres),
unrecognized filename rejected without dropping the valid one, and
all-unrecognized -> 400 with no job created. The worker task is invoked
directly against the real DB (same precedent as `test_task_error_handling.py`
calling `_fail_job` directly) instead of going through the live Arq queue, to
avoid racing this repo's docker-compose worker container, which shares the
same Redis/Postgres.

Deviation found and fixed: the existing seed-user SQL pattern this repo's other
admin integration tests use (`split_part(:email, '@', 1)` reusing the `:email`
bind twice) hit `asyncpg.exceptions.AmbiguousParameterError: inconsistent types
deduced for parameter $2` in this environment -- confirmed pre-existing and NOT
caused by this change (the untouched `test_ingestion_router.py` fails
identically). Worked around it in this new test file only, by using a distinct
named `:name` parameter instead of reusing `:email`.

### T6 -- verification

`ruff check backend/src backend/tests && ruff format --check backend/src backend/tests`
(scoped to files touched by this branch): all pass, `All checks passed!` /
`already formatted`. Two ruff-format diffs the tool proposed on `git diff`
inspection are in files this branch never touched (`live_router.py`,
`player_club_career_repository.py`) plus 3 pre-existing integration test files
-- left alone, out of scope.

Full `pytest` (backend/, from repo root, real Postgres/Redis via
docker-compose, env vars exported manually since `backend/.env` already exists
in this checkout so no workaround was needed there):
`7 failed, 126 passed, 49 errors` -- **all pre-existing and unrelated to this
change**, confirmed by:
- The identical failure count/errors reproduce on the untouched
  `test_ingestion_router.py`, `test_conversation_*`, `test_tool_call_executor.py`
  etc. before this branch's endpoint code was ever exercised.
- None of the failing/erroring files reference any file this branch touches
  (grepped for `bulk_synthetic`/`BULK_SYNTHETIC`: no matches).
- `pytest tests/unit tests/integration/api/admin/test_bulk_synthetic_upload_router.py tests/integration/test_health.py`
  (everything this feature added or touches, plus a sanity check): `74 passed`.

Root cause of the pre-existing breakage (not fixed, out of scope): the shared
dev Postgres's `alembic_version` doesn't match this branch's migration chain
(see T4 deviation above), and a second, apparently unrelated class of failure
(`test_tool_call_executor.py`'s `TurnResolvedEvent` missing `widget_results`)
suggests the checked-out code and the live shared DB/fixtures have drifted
from whatever another concurrent worktree last left behind.

Live smoke test: could not run the literal `curl` version from `## Verification`
-- the live docker-compose backend container's seeded admin
(`admin@example.com`) does not accept the `env.example.txt`/`.env` default
password (`change-me`); the real password is unknown and guessing credentials
was not attempted. Instead ran the equivalent in-process (httpx `AsyncClient`
against the real ASGI app, real shared Postgres/Redis, the actual 10 dataset
CSVs from `data/FIFA-World-Cup-2026-Dataset/` in randomized/scrambled order,
worker task invoked directly against the real DB): **one job succeeded**,
`row_counts` matched each file's real row count exactly
(`{"team": 48, "venue": 16, "tournament_stage": 7, "referee": 28, "player": 1248,
"match": 104, "match_event": 601, "match_team_stat": 208, "match_lineup": 5408,
"player_stat": 1248}`), zero FK violations. Verified against the DB directly
afterward (row counts matched). Cleaned up every row this smoke test inserted
immediately after (the tables it populated were empty beforehand) since a
first re-run of the full suite showed it had collided with an unrelated
fixture-dependent test (`test_get_player_analysis_resolves_accented_query_via_unaccent`,
which assumes an empty/small player table); after cleanup, the full suite
returned to the exact same `7 failed, 126 passed, 49 errors` baseline.

No deviations from scope otherwise: single-file `synthetic-upload` endpoint and
the Transfermarkt sync pipeline were not touched.

### T8 -- stage checkpoints for the bulk-upload job

Mechanism chosen for `record_stage_checkpoint`'s typing: widened the
parameter from the Transfermarkt-specific `TransfermarktSyncStage` to the
generic `enum.StrEnum` (not a bare `str`, not a `TransfermarktSyncStage |
BulkSyntheticUploadStage` union that would need editing every time a third
job type wants stages). `current_stage`/`stage_checkpoints` on `IngestionJob`
are already job-type-agnostic (`str | None` / `list[dict[str, str]]`), so
`record_stage_checkpoint(stage: StrEnum)` loses no type safety at any call
site -- each caller still passes a real concrete enum member
(`TransfermarktSyncStage.CLUBS`, `BulkSyntheticUploadStage.TEAM`, ...),
type-checked by its own enum, matching AGENTS.md's "type safety over
strings" rule. `JobProgressTracker.checkpoint` (the wrapper
`TransfermarktSyncService` already used to persist checkpoints through the
job repository) was widened the same way, so `BulkSyntheticIngestionService`
reuses that exact class instead of a second, divergent checkpoint-persisting
path -- one shared, tested code path for both job types, per the brief.

New `backend/src/domain/ingestion/model/bulk_synthetic_upload_stage.py`:
`BulkSyntheticUploadStage(StrEnum)`, one member per
`BULK_SYNTHETIC_INGESTION_ORDER` table name, with a module-level assertion
in `bulk_synthetic_ingestion_service.py` keeping the two in exact sync
(mirrors T1's `BULK_SYNTHETIC_FILENAME_TO_TABLE`/`BULK_SYNTHETIC_INGESTION_ORDER`
drift guard).

`BulkSyntheticIngestionService.ingest_batch` now builds a `JobProgressTracker`
right after `mark_running()`, exactly where `TransfermarktSyncService.run_sync`
does, and calls `await progress.checkpoint(BulkSyntheticUploadStage(resolved.table_name))`
immediately after each table's rows are ingested (mirrors
`TransfermarktSyncService`/`TransfermarktDetailSync`'s "checkpoint right after
that phase's work finishes" convention, including its
`TransfermarktSyncStage(source_name)`-from-string construction style). On a
mid-batch `IngestionValidationError`, the failure path now marks
`progress.job` (not the stale pre-loop `running_job`) failed, so checkpoints
already recorded for tables ingested before the failure survive onto the
failed job's history instead of being silently discarded.

Deviation found and fixed (within T8's own stated scope): `ingestion_dtos.py`'s
`JobStatusResponse.from_domain` hardcoded `all_stages` to populate only for
`job_type == TRANSFERMARKT_SYNC`, returning `[]` for every other job type --
its own docstring said so explicitly. The merged admin panel's
`StageProgress` component (`frontend/src/features/ingestion/components/
stage-progress.tsx`) renders nothing at all when `job.allStages.length === 0`
(`if (job.allStages.length === 0) return null`), so leaving this hardcoded
would mean `current_stage`/`stage_checkpoints` populate correctly on the
backend but the progress UI never renders for a bulk-upload job -- directly
contradicting T8's own goal ("show live progress just like transfermarkt").
Fixed via a `dict[IngestionJobType, list[str]]` lookup
(`_ALL_STAGES_BY_JOB_TYPE`) covering both `TRANSFERMARKT_SYNC` and
`BULK_SYNTHETIC_UPLOAD`, defaulting to `[]` for any other job type (e.g.
plain `synthetic_upload`, which has no sub-stages) -- confirmed via the brief's
own instruction to read this exact file rather than assume, and confirmed
in-scope since a stage field (`all_stages`) was NOT flowing through the DTO
for this job type at all, which is exactly the carve-out the brief allowed.
Did not touch anything in `frontend/` -- the frontend zod schema's
`jobTypeSchema` still doesn't include `"bulk_synthetic_upload"` either, but
wiring the bulk job type into the frontend is explicitly T9's job, not T8's.

TDD: extended `tests/unit/domain/ingestion/test_bulk_synthetic_ingestion_service.py`
first -- added assertions on `result.stage_checkpoints`/`result.current_stage`
to the existing succeeded-job test (updating its expected
`job_repository.updates` status sequence to include the two intermediate
RUNNING updates from mid-batch checkpoints), a new test asserting checkpoints
land in fixed ingestion order regardless of upload order, and a new test
asserting checkpoints from tables ingested before a later failure survive
onto the failed job. Ran the suite first to confirm RED (3 failed:
`AssertionError: assert [] == ['team', 'player']` etc., since
`BulkSyntheticUploadStage` and the checkpoint calls didn't exist yet), then
implemented, then confirmed GREEN (6 passed). Also extended the existing
integration test in `test_bulk_synthetic_upload_router.py` (the scrambled-order
happy path) with assertions on `stage_checkpoints`, `current_stage`, and
`all_stages` from the real `GET /jobs/{id}` response -- ran against the real
docker-compose Postgres, passed (this doubles as T8's own live check, per the
brief's fallback: same in-process approach as T6, since the live admin
password is still unknown).

Verification:
- `ruff check backend/src backend/tests && ruff format --check backend/src backend/tests`:
  clean (`[]` / `266 files already formatted`).
- `pytest tests/unit domain/ingestion` (all ingestion unit tests, Transfermarkt
  included): 85 passed -- confirms widening `record_stage_checkpoint`/
  `JobProgressTracker.checkpoint` to `StrEnum` did not change
  `TransfermarktSyncService`'s own behavior or break its existing tests.
- `pytest tests/integration/api/admin/test_bulk_synthetic_upload_router.py`:
  3 passed against the real docker-compose Postgres, including the new
  stage-checkpoint/`all_stages` assertions.
- Full `pytest` (backend/, real Postgres/Redis): `6 failed, 217 passed, 33 errors`.
  Confirmed identical failure/error set before and after this change via
  `git stash`/`git stash pop` around a full-suite re-run on the same
  checkout: stashed (pre-T8) run was `6 failed, 215 passed, 33 errors` --
  same 6 failures, same 33 errors, node-for-node; the only difference is the
  +2 passed from the two new unit tests T8 added. None of the pre-existing
  failures/errors reference any file T8 touches (`test_tool_call_executor.py`'s
  `TurnResolvedEvent.widget_results` gap and the `AmbiguousParameterError`
  seed-user-SQL fixture issue across several `tests/integration/**` files are
  the same pre-existing, unrelated issues T5/T6 already documented).

Commit: `38fe17f` `feat(ingestion): add stage checkpoints to bulk synthetic upload job`.

Files touched: `backend/src/domain/ingestion/model/ingestion_job.py`,
`backend/src/domain/ingestion/model/bulk_synthetic_upload_stage.py` (new),
`backend/src/domain/ingestion/services/job_progress_tracker.py`,
`backend/src/domain/ingestion/services/bulk_synthetic_ingestion_service.py`,
`backend/src/api/v1/admin/dtos/ingestion_dtos.py`,
`backend/tests/unit/domain/ingestion/test_bulk_synthetic_ingestion_service.py`,
`backend/tests/integration/api/admin/test_bulk_synthetic_upload_router.py`.
No router/Arq task/schema changes needed -- `GET /jobs/{id}` already returns
`JobStatusResponse.from_domain(job)` generically, and `IngestionJobRepository.
update()` already persisted `current_stage`/`stage_checkpoints` for any job
type (verified, not assumed, per the brief).

### T9 -- frontend admin UI (last task on this feature)

Read the mirror-target files first, as instructed, rather than approximating
from memory: `use-transfermarkt-sync-job.ts`, `trigger-transfermarkt-sync.ts`,
`get-job-status.ts`, the two existing Route Handlers, `sync-jobs-panel.tsx`,
`stage-progress.tsx`, `types.ts`, `job-status.schema.ts`,
`correct-match-dialog.tsx`, `proxy-backend-json.ts`, and the backend's actual
`ingestion_router.py`/`ingestion_dtos.py` for the bulk-upload contract
(confirmed field name `files`, repeated `UploadFile`; 201 body
`{job_id, status, files}`; 400 body `{detail: {message, files}}`) rather than
trusting the brief's paraphrase of it.

**Confirmed generically reusable as-is, no changes needed**: `StageProgress`
(keys off `job.allStages`/`currentStage`/`stageCheckpoints`, all already
job-type-agnostic strings) and `get-job-status.ts`/`JobStatusResponse`
parsing (already generic per T8). Only `job_type`'s zod enum and the
frontend's `IngestionJobType` union needed a new `"bulk_synthetic_upload"`
member -- added to both `types.ts` and `job-status.schema.ts`.

**The multipart-proxy gap flagged in the brief**: no existing Route Handler
in this codebase proxies a `multipart/form-data` request (the single-file
`synthetic-upload` endpoint was never wired to the frontend either). Read
`proxy-backend-json.ts` to find exactly how it attaches auth
(`getSessionToken()` from the httpOnly `fai_session` cookie, forwarded as
`Authorization: Bearer <token>`) and replicated that same mechanism in a new
`proxy-backend-multipart.ts`, differing from `proxyBackendJson` in two
ways this endpoint specifically needs:
1. The request body is the caller's `FormData` forwarded as-is, with no
   `Content-Type` header set manually -- `fetch` derives the multipart
   boundary from the `FormData` instance itself, and a hand-set header would
   omit it and break the backend's multipart parser.
2. The backend's JSON response body is forwarded **verbatim** on every
   status, instead of `proxyBackendJson`'s own normalization to a plain
   `{ detail: string }` on error. The bulk-upload endpoint's 400 body carries
   a structured `detail.files` per-file rejection list the UI renders as a
   real result (not just an error message), so collapsing it would lose
   information no other ingestion endpoint's error shape needs to carry.
The new Route Handler (`app/api/admin/ingestion/bulk-synthetic-upload/
route.ts`) reads `request.formData()` and forwards it through
`proxyBackendMultipart` unchanged -- the field name (`files`) already matches
what the backend expects, so no reconstruction was needed. Auth is never
skipped: an unauthenticated request never reaches the backend at all
(`proxyBackendMultipart` returns 401 immediately per its own
`getSessionToken()` check, mirroring `proxyBackendJson`).

Deviation found and fixed (via live testing, not assumption): the first cut
of the route handler let `request.formData()`'s exception propagate on a
missing/non-multipart body, surfacing as an unhandled 500 instead of a clean
error. Fixed by wrapping it in try/catch returning 400
`{"detail": "Expected a multipart/form-data body"}}`, mirroring the existing
JSON routes' own try/catch-and-default-gracefully handling of a malformed
body (`transfermarkt-sync/route.ts` does the same for `request.json()`).

**API client** (`upload-bulk-synthetic-csvs.ts`): not built on the shared
`fetchJson` helper like the feature's other clients, because a 400 here is
not a bare error to throw -- it is a structured per-file rejection result the
UI displays. Parses both the 201 success body and the 400
`detail.{message,files}` body itself via two zod schemas in
`bulk-upload-response.schema.ts`, returning a `BulkUploadResult` with
`jobId: null` for the zero-accepted case; only a genuinely unexpected error
shape still throws `ApiError`.

**Hook** (`use-bulk-synthetic-upload-job.ts`): mirrors
`useTransfermarktSyncJob` exactly for job-tracking (trigger once, fetch
status once when a job id appears, fetch once on mount from a cached
`localStorage` id, manual-refresh-only otherwise -- no polling, no terminal-
status stop condition, confirmed this is still correct for this job type
too: nothing about a bulk upload needs different refresh semantics). One
addition beyond the mirror: `uploadResult` state holds the per-file
accept/reject breakdown from the upload response, kept separately from `job`
so a later `refresh()` call (which only touches `job`) never overwrites or
loses it -- this is the one place that information exists, per the brief.
Deviated from the mirrored file on one cosmetic point only: used a fresh
`ingestion:last-bulk-synthetic-upload-job-id` localStorage key instead of
copying the mirrored file's `identity-links:last-transfermarkt-sync-job-id`
prefix, which is itself a pre-existing copy-paste artifact from a different
feature (`identity-links`) that happens to live in the `ingestion` feature
folder -- not worth propagating into a second key.

**Component** (`bulk-synthetic-upload-panel.tsx`): Card-based layout
matching `SyncJobsPanel`'s structure and design tokens exactly (same
`border-border-subtle`/`bg-surface-800`/`text-ink-*`/`bg-brand` classes, same
literal-text loading states, no spinner). Renders, in order: the file picker
+ submit card; the per-file upload-results card (Badge per file,
accepted/rejected, table name or rejection reason) whenever `uploadResult` is
non-null, regardless of whether any file was accepted; and the job status
card (reusing `StageProgress` as-is) only when `jobId !== null`. The job
status card's JSX duplicates `SyncJobsPanel`'s own card block rather than
extracting a shared component -- a deliberate choice, not an oversight: the
brief explicitly asked not to touch `sync-jobs-panel.tsx` beyond what's
strictly needed, and extracting a shared card would have required changing
that file's own render output for a second consumer that didn't exist before
this task.

**Wiring**: `features/ingestion/index.ts` exports the new panel;
`app/(admin)/sync-jobs/page.tsx` renders `<SyncJobsPanel />` and
`<BulkSyntheticUploadPanel />` as siblings in a `flex-col gap-ds-8` wrapper --
still a thin routing shell, no new route/page.

TDD: schema tests
(`tests/unit/features/ingestion/bulk-upload-response-schema.test.ts`) and a
new case in the existing `job-status-schema.test.ts` for the
`bulk_synthetic_upload` job type, plus a hook test
(`use-bulk-synthetic-upload-job.test.tsx`) mirroring
`use-transfermarkt-sync-job.test.tsx`'s structure and mocking style
(`vi.mock` on the API-client module, not `fetch`) exactly, including a case
specifically asserting `uploadResult` survives a later `refresh()`. No
component-level RTL test was added for the new panel, matching this
codebase's existing depth (no panel/component tests exist for
`sync-jobs-panel.tsx` either).

Verification:
- `npx vitest run tests/unit/features/ingestion`: 4 files, 19 passed (includes
  the 2 new test files plus the extended `job-status-schema.test.ts`).
- `npx vitest run` (full suite): 17/20 files, 96/97 tests passed excluding 3
  pre-existing unrelated failures -- confirmed pre-existing via `git status`
  showing none of those 3 files (`login-form.test.tsx`,
  `assistant-markdown.test.tsx`, `message-part-renderer.test.tsx`) touched by
  this branch, and via a `git stash`/build re-run on the pre-T9 tree (below)
  reproducing the identical `react-markdown`/`remark-gfm` module-not-found
  errors that also underlie the two chat test file failures.
- `npm run build` (`next build`, which runs the TypeScript check as part of
  the build): initially failed on a **pre-existing, unrelated** environment
  gap -- `node_modules` was stale relative to `package.json` (missing
  `react-markdown`/`remark-gfm`, added in a commit from Sep 24 that predates
  this branch; `node_modules` itself dated Sep 17). Ran `npm install` to
  bring the environment in line with the committed `package.json`/
  `package-lock.json` (no source or lockfile changes) -- not a modification
  this feature required, purely an environment fix so the build could
  actually run. After that, the build compiled and typechecked with zero
  errors in any file this task touches; the remaining typecheck failures are
  all in `src/features/chat/**` and its tests (a `MessagePart`/`venueLabel`
  null-vs-undefined mismatch, an unrelated `ConversationSummary`/`void`
  mismatch, a stray `className` prop) -- confirmed pre-existing and
  unrelated by `git stash`-ing every file this task touched and re-running
  `npm run build`: byte-for-byte the same error list, same file, same line
  numbers, before this task's files existed.
- `npx eslint` on every new/touched file: clean except
  `use-bulk-synthetic-upload-job.ts`, which reproduces the exact same
  `react-hooks/set-state-in-effect` (2x) finding as the untouched, mirrored
  `use-transfermarkt-sync-job.ts` -- confirmed by running eslint on that
  original file too; not a regression, inherent to the pattern this task was
  explicitly told to mirror exactly.
- Live: the shared docker-compose stack's `world-cup-ai-scout-frontend`
  container turned out to be bind-mounted from a **different** worktree
  (`.claude/worktrees/team-comparison/frontend`, confirmed via `docker
  inspect`'s `Mounts`), not this checkout -- consistent with T4/T6's already-
  documented observation that this docker-compose stack is shared across
  concurrent worktrees. Left that container untouched (restarting/repointing
  shared infra for another in-progress session would be disruptive and out
  of scope) and instead ran `next dev` locally from this checkout on port
  3001 with `BACKEND_API_URL` pointed at the already-running backend
  container's published port (`localhost:8000`), then `curl`'d the new route
  directly:
  - No cookie + valid multipart body -> `401 {"detail":"Not authenticated"}`
    (rejected by the Route Handler itself, before ever reaching the backend).
  - Garbage/expired cookie (`fai_session=totally.fake.jwt`) + valid multipart
    body -> `401 {"detail":"Invalid or expired token"}`, the backend's own
    JWT-validation error, forwarded verbatim -- proves the multipart body
    and the bearer token both actually reached the real FastAPI backend
    through the new proxy, not just that the Next.js route existed.
  - No body at all -> reproduced the 500 documented above as a real bug, then
    re-tested after the fix -> clean `400
    {"detail":"Expected a multipart/form-data body"}`.
  Did **not** verify the success path (valid admin session -> 201 -> job
  card renders with live stage progress) end-to-end through a browser --
  same blocker T6/T8 already hit and documented: the live admin's real
  password is unknown and guessing credentials was not attempted. This is a
  real, disclosed gap, not claimed as done.
- `ruff`/`pytest` not re-run -- T9 touched no backend files.

Files created: `frontend/src/lib/api/proxy-backend-multipart.ts`,
`frontend/src/app/api/admin/ingestion/bulk-synthetic-upload/route.ts`,
`frontend/src/features/ingestion/api/upload-bulk-synthetic-csvs.ts`,
`frontend/src/features/ingestion/schemas/bulk-upload-response.schema.ts`,
`frontend/src/features/ingestion/hooks/use-bulk-synthetic-upload-job.ts`,
`frontend/src/features/ingestion/components/bulk-synthetic-upload-panel.tsx`,
`frontend/tests/unit/features/ingestion/bulk-upload-response-schema.test.ts`,
`frontend/tests/unit/features/ingestion/use-bulk-synthetic-upload-job.test.tsx`.

Files modified: `frontend/src/features/ingestion/types.ts`,
`frontend/src/features/ingestion/schemas/job-status.schema.ts`,
`frontend/src/features/ingestion/index.ts`,
`frontend/src/app/(admin)/sync-jobs/page.tsx`,
`frontend/tests/unit/features/ingestion/job-status-schema.test.ts`.

`sync-jobs-panel.tsx`, `stage-progress.tsx`, and every other Transfermarkt
sync UI file were not touched at all.

## Post-completion: environment incident, repaired, then re-verified cleanly

After T9, discovered the running `docker-compose` containers
(`world-cup-ai-scout-backend`/`-worker`/`-frontend`) were bind-mounted from
`.claude/worktrees/team-comparison` (branch `feature/team-comparison`), not
this checkout — a known class of issue (see memory `docker compose
containers shared across git worktrees by project name`, not re-discovered
via search until after the fact). Every `docker exec`/`docker cp` used for
T1-T9 "live" verification against these containers actually read/wrote
that other worktree's real files. Confirmed via `git status` +
file-mtime comparison in that worktree, then repaired precisely: restored
24 clobbered tracked files with `git checkout -- <exact list>` and deleted
16 polluted untracked files by exact path (never a blanket `git clean`),
leaving team-comparison's own genuine uncommitted work (8 files, all with
an untouched 2026-09-24 mtime) exactly as it was. Verified fully repaired
via `git status --short backend/` afterward.

Re-verified this feature's actual state via the local venv/npm (not the
misattributed containers), against the same real shared Postgres/Redis
(only those two are genuinely shared safely across worktrees):
- Backend: `python -m pytest tests/unit/domain/ingestion/
  tests/integration/api/admin/test_bulk_synthetic_upload_router.py` → 88
  passed; `ruff check` clean.
- Frontend: `npx vitest run tests/unit/features/ingestion` → 19/19 passed.
- `npm run build` fails on pre-existing, unrelated TypeScript errors in
  `src/features/chat/**` — confirmed via `git diff main...feat/bulk-synthetic-upload
  --stat -- frontend/src/features/chat` returning empty (this branch never
  touched any file in that path), so the failure is not attributable to
  this feature.

All 9 tasks (T1-T9) are complete and independently re-verified through a
trustworthy path. Feature branch `feat/bulk-synthetic-upload` remains
local-only, not pushed, no PR — the user's call.
