# Feature: golden-set-tests

## Objective
A golden set for the chat system: fixed questions/cases with expected answers derived from a committed,
known fixture dataset, covering every known case of the system. Two layers:
- Layer A (deterministic, no LLM): real tool handlers + real repositories on seeded Postgres, compared
  to fixture-derived expected values. Runs with the integration suite (needs local Postgres).
- Layer B (opt-in `llm_eval`): the same golden questions through the real LLM with real repositories on
  the fixture; asserts tool choice, arguments and that answers state the fixture's facts.

## Why
Complements the counterfactual evals (PR #39, fake repos): proves the whole path (LLM -> tool -> real SQL
repository -> answer) returns the right known facts, and pins every known behavior as a regression net.

## Scope (authorized)
- New `backend/tests/golden/` package: fixture seeding (raw SQL, dedicated ID range, always cleaned up),
  case definitions, deterministic tests (Layer A), LLM tests (Layer B).
- Branch `claude/golden-set-tests`, stacked on `claude/llm-data-validation-a22f7e` (PR #39) because it
  reuses the eval harness. PR base = that branch until #39 merges, then retarget to main.
- Out of scope: production code changes; running Layer B live (no OPENROUTER_API_KEY here).

## Known cases to cover
7 tools happy paths; team code / exact / substring / accent / misspelled name resolution; ambiguous
player name (two "Luis Suarez"); two matches between the same teams (stage/date disambiguation);
identity link approved vs pending; player never at the World Cup (Transfermarkt career fallback,
RETIRED/FREE team codes); goalkeeper stats; query_player_stats allowlist/ops/GK-only fields/empty
result/invalid filter; comparison errors (same entity, not found); invalid tool args; tool loop cap and
clarification request (deterministic via scripted client); match-selector chip directive
(`_build_match_directive`, untested today); no-tool questions; unanswerable questions.

## Constraints
- Real Postgres, no mocks/patch (AGENTS.md). Files < 400 lines. English artifacts.
- Test DB is the shared local dev DB (docker postgres :55432): fixture rows use a dedicated ID range,
  are cleaned up in teardown, and expected values never depend on peer rows (no percentiles).
- ~400 authored lines per task is an advisory heuristic only.

## Resolved config
- TDD: strict mode; Layer A has observable RED/GREEN (run against DB). Layer B RED not observable
  without API key (disclosed).
- Runner A: `cd backend && pytest tests/golden`; Runner B: `pytest -m llm_eval tests/golden`.
- Delivery: ask-on-risk; stacked on PR #39.

## Tasks
- [x] T1 Fixture seeding + case definitions (committed mini tournament, cleanup) — delegated writer
- [x] T2 Layer A deterministic golden tests for all known cases — delegated writer
- [x] T3 Layer B LLM golden tests (llm_eval) — delegated writer
- [x] T4 Verify, commit work units, open PR (base: claude/llm-data-validation-a22f7e)

## Route declaration
Mapping needed 4+ files (done via one Explore worker); writer touches 2+ non-trivial files per task, so
one bounded sonnet writer per task, sequential, single writer thread.

## Acceptance criteria
- Layer A passes against the local Postgres; leaves no fixture rows behind.
- Layer B collects with `-m llm_eval`, is deselected by default.
- ruff clean; existing unit + eval collection unaffected.

## Progress / evidence
- Layer A: 113 deterministic golden tests pass against local Postgres (twice, idempotent), fixture leaves 0 rows; mutation check (fixture goals 4->5) failed 6 tests.
- Layer B: 44 opt-in llm_eval cases; collected, deselected by default; scripted-client smoke: checks pass on 51 correct variants and fail on 55 hallucinated ones. Never run against the live model (no API key).
- unit 148 passed, evals collect 39, ruff clean.
- Commits: afca91e (fixture + Layer A), harness tweak, Layer B.

## Findings (possible production bugs, not changed)
1. get_team_analysis / get_team_comparison are not accent-insensitive ("Curacao" does not find "Curaçao"); players and matches are.
2. Ambiguous player name is silent: `_resolve_player` takes .first() with no ORDER BY.
3. get_match_analysis with an invalid `date` raises an uncaught ValueError that aborts the turn.
4. After a penalty-shootout loss the standing label reads "out 1-1 to Karsovia" (pinned as-is).

## Next step
Run `cd backend && pytest -m llm_eval tests/golden` with a real OPENROUTER_API_KEY; decide on fixes for the findings.
