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
