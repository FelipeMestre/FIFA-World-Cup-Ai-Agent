# Feature: no-data-tests

## Objective
Empty-data scenario tests for every case of the system: what happens when the data a request needs does
not exist (unknown entity, entity with no stats/matches/career, filters matching nothing, history
empty), proving the system reports "no data" and the LLM never invents facts.
- Layer A (deterministic, default suite): real tool handlers + real repos on the golden fixture extended
  with deliberately empty entities, plus nonexistent names. Needs local Postgres like the golden set.
- Layer B (opt-in `llm_eval`): the same no-data cases through the real LLM; answer must say data is
  missing and state no invented numbers/facts.

## Why
The golden set (PR #40) covers cases with data. The hallucination risk concentrates where tools return
nothing; each tool has several distinct no-data shapes worth pinning.

## Scope (authorized)
- Branch `claude/no-data-tests`, stacked on `claude/golden-set-tests` (PR #40) because it reuses the
  golden fixture, seeding and LLM harness. PR base = that branch until #40 merges.
- New files under `backend/tests/golden/` (or `backend/tests/no_data/` if cleaner): additional fixture
  rows for empty entities (dedicated ID ranges, always cleaned), Layer A tests, Layer B cases.
- Chat-service level empty cases (first message / empty history / empty cache) where testable
  deterministically.
- Out of scope: production code changes (findings are reported, not fixed); running Layer B live.

## Constraints
- Real Postgres, no Mock/patch; files < 400 lines; English; expected values as constants; no percentile
  or peer-dependent assertions; fixture uses only its dedicated ID ranges and cleans up.
- ~400 authored lines per task is an advisory heuristic only.

## Resolved config
- TDD strict; Layer A has observable RED/GREEN, Layer B RED not observable (no API key).
- Runner A: `cd backend && pytest tests/golden` (or the new dir); Runner B: `pytest -m llm_eval ...`.
- Delivery: ask-on-risk; stacked on PR #40; size:exception requested as before (cached from #39).

## Tasks
- [ ] T1 Map no-data shapes per tool/case; extend fixture with empty entities; Layer A tests
- [ ] T2 Layer B LLM no-data cases
- [ ] T3 Verify, commit work units, open PR (base: claude/golden-set-tests)

## Route declaration
One bounded sonnet writer per task, sequential, single writer thread (writes 2+ non-trivial files and
needs reading of tools, repos and golden fixture).

## Acceptance criteria
- Layer A green on local Postgres, idempotent, zero leftover rows.
- Layer B collects with `-m llm_eval` and is deselected by default; scripted smoke shows checks pass on
  honest no-data answers and fail on hallucinated ones.
- ruff clean; unit/evals/golden suites unaffected.

## Progress / evidence
(none yet)

## Next step
T1.
