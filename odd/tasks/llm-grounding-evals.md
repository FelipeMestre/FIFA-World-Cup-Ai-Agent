# Feature: llm-grounding-evals

## Objective
Systematically validate that the chat LLM answers only from tool output (no hallucination) with opt-in
counterfactual evals against the real model (`pytest -m llm_eval`).

## Problem / why
User wants proof the LLM relies on tool data. Counterfactual evals swap a tool's data for altered values
and assert the answer follows the tool. Player analysis is done (5 tests, uncommitted). This iteration
extends coverage to every other tool, and to questions that need no tool.

## Scope (authorized)
- Generalize `backend/tests/evals/grounding_harness.py` (fake team/player/match repos, all optional).
- One eval module per tool under `backend/tests/evals/`: get_team_analysis, get_match_analysis,
  get_player_comparison, get_team_comparison, query_player_stats, get_current_utc_time.
- A module for no-tool questions (greeting, capabilities, off-topic, unanswerable-by-tools): assert no
  invented stats and sensible tool usage.
- Out of scope: production code changes, running against the real model (no API key in worktree).

## Constraints
- Real fakes, no Mock/@patch (AGENTS.md). Files under 400 lines. English artifacts.
- Real handler/registry/executor/system prompt/schemas; only repositories are faked.
- Planning heuristic ~400 authored changed lines per task (advisory only).

## Resolved config
- TDD: strict mode enabled in user config, but RED is not observable for live-LLM evals without an API
  key; disclosed. Functional checks: ruff, `pytest --collect-only -m llm_eval`, default run deselects,
  handler smoke checks with fake repos, existing unit suite.
- Runner: `cd backend && pytest -m llm_eval tests/evals`.
- Delivery strategy: ask-on-risk (default). Forecast < 400 lines per slice is not met overall; branch
  is already a feature branch, one PR slice per tool group if needed.

## Tasks
- [ ] T1 Generalize harness (optional repos, `run_turn`, keep player tests green on collect) — route: delegated writer
- [ ] T2 Per-tool counterfactual evals (team, match, player comparison, team comparison, ranking, utc time) — route: delegated writer
- [ ] T3 No-tool question evals — route: delegated writer
- [ ] T4 Verify (ruff, collect-only, default deselect, handler smoke, unit suite) and commit work units

## Route declaration
Mapping needs 4+ domain model files and the writer touches 2+ non-trivial files, so mandatory delegation
triggers fire: one bounded writer (sonnet), single writer thread.

## Acceptance criteria
- `pytest -m llm_eval --collect-only` lists all new evals; plain `pytest tests/evals` deselects them.
- ruff check/format clean; existing unit suite passes.
- Every tool eval asserts the tool was called and that the answer follows altered tool data.

## Progress / evidence
- Player analysis evals (5) done earlier in session; collected OK, not run against live model.

## Next step
Delegate T1-T3 to one writer, then verify and commit.
