# Match Analysis tool — backend

## Objective
Add a `get_match_analysis` chat tool (and its supporting domain model + repository)
so the already-built frontend `match_widget` (MatchSummary type, widget-match.tsx,
panel-match.tsx) has real data to render: scoreboard, possession/shots split bars,
key events, Player of the Match, full team stats, event timeline, lineups by
GK/DEF/MID/FWD.

## Why
User request. Frontend widget contract already exists and is unused
(`MatchWidgetPart` is a stub in chat_dtos.py). This closes the gap on the backend
side, following the existing `get_team_analysis`/`get_player_analysis` pattern.

## Scope / design decisions (confirmed with user)
- Match identified by two team names (home/away, free text) resolved the same
  fuzzy way team_analysis resolves one name; optional stage/date to disambiguate
  repeat fixtures.
- `match_event.event_type` confirmed values (from live DB): `Goal`, `Own Goal`,
  `Assist`, `Yellow Card`, `Red Card`, `VAR Review`, `Penalty Shootout Goal`,
  `Penalty Shootout Miss`. No `Substitution` event type exists — substitutions
  are dropped from the timeline (data doesn't support a clean sub event); only
  `match_lineup.is_starting_xi`/`minutes_played` distinguish starters/subs used.
- `Assist` is a separate event row from `Goal`/`Own Goal`; pair them by
  `match_id` + `minute` + `team_id`.
- Player of the Match: prefer `match.player_of_the_match_id` (canonical FK),
  ignore `match_team_stat.player_of_the_match` (legacy dup free-text field).
- Ambiguous match resolution (0 or 2+ plausible matches for the given team
  names/stage/date): repository returns a distinct "ambiguous" result carrying
  candidate summaries instead of a single `MatchAnalysis`; tool handler packs
  those candidates into the JSON `content` string (same round-trip pattern
  `get_player_analysis` already uses for "not found") so the model can ask the
  user to disambiguate — no new plumbing needed for this, it's the existing
  tool-result-to-model flow.

## Constraints
- Follow existing layered architecture exactly (domain model / infra interface
  + repository / chat tool / registry+router wiring) — mirror
  `get_team_analysis`/`team_analytics_repository.py` file-for-file in structure.
- SQL-first aggregation (joins/grouping in Postgres, not Python), per AGENTS.md.
- Async routes/repositories throughout (`AsyncSession`).
- No new abstractions beyond what this tool needs.

## Tasks
- [x] T1: `backend/src/domain/match_analytics/model/match_analysis.py` — Pydantic
      read-model tree (camelCase via alias_generator) matching frontend
      `MatchSummary` shape exactly (scoreboard, stats rows, events, timeline,
      playerOfMatch, lineups grouped by position, footerCaption), plus an
      ambiguous-result model carrying match candidates.
- [x] T2: `backend/src/infra/postgres/interfaces/match_analytics_repository_interface.py`
      — `Protocol` with `get_match_analysis(home_team, away_team, stage=None,
      date=None) -> MatchAnalysis | MatchAnalysisAmbiguous | None`.
- [x] T3: `backend/src/infra/postgres/repositories/match_analytics_repository.py`
      — SQLAlchemy impl: fuzzy team-name resolution (reuse team_analytics'
      approach), match lookup/disambiguation, SQL-first aggregation of
      match/match_event/match_team_stat/match_lineup/national_team/
      tournament_stage/player/player_stat, `get_match_analytics_repository`
      FastAPI provider. Pure shape-building split into
      `backend/src/infra/postgres/repositories/_match_analytics_builders.py`
      to keep both files under the project's 400-line cap.
- [x] T4: `backend/src/domain/chat/tools/get_match_analysis.py` — tool schema
      (home_team_name, away_team_name, optional stage/date args), args model
      (`extra="forbid"`), handler builder following get_player_analysis.py's
      exact shape, including the ambiguous-candidates JSON content path.
- [x] T5: wired into `backend/src/domain/chat/tools/registry.py` (schema list +
      build_tool_registry param + registration), `backend/src/api/v1/chat/
      routers/chat_router.py` (widget-type map + repository dependency), and
      dropped the "Not implemented yet" note on `MatchWidgetPart` in
      `backend/src/api/v1/chat/dtos/chat_dtos.py`.
- [x] T6: verification — ruff check/format clean on all touched files;
      `pytest` full suite run, 7 new integration tests added (RED confirmed
      first, then GREEN), 127 passed / 7 failed / 3 errors, all 7
      failures + 3 errors pre-existing and unrelated (confirmed against the
      unmodified baseline via a temporary WIP stash — same exact failures,
      119 passed on baseline vs 127 with this change, i.e. +8 new tests, 0
      regressions).

## TDD mode
Strict TDD Mode is enabled globally (user's CLAUDE.md). Runner: `pytest`
(`asyncio_mode = "auto"`, configured in `pyproject.toml`). Repository test
written first against `_SqlAlchemyMatchAnalyticsRepository.get_match_analysis`
(module didn't exist yet), confirmed RED (`ModuleNotFoundError`), then
implemented until GREEN (8/8 passing).

## Acceptance criteria
- [x] `get_match_analysis` tool registered and callable from chat, returns
  `widget_data` shaped exactly like `MatchSummary` for an unambiguous query.
- [x] Ambiguous/no-match queries return informative JSON content, no crash.
- [x] ruff clean; existing test suite still passes (pre-existing unrelated
  failures verified via baseline comparison, not caused by this change).

## Progress / evidence

**Files created:**
- `backend/src/domain/match_analytics/model/match_analysis.py` (122 lines)
- `backend/src/infra/postgres/interfaces/match_analytics_repository_interface.py` (35 lines)
- `backend/src/infra/postgres/repositories/match_analytics_repository.py` (279 lines)
- `backend/src/infra/postgres/repositories/_match_analytics_builders.py` (249 lines)
- `backend/src/domain/chat/tools/get_match_analysis.py` (117 lines)
- `backend/tests/integration/infra/test_match_analytics_repository.py` (8 tests)

**Files modified:**
- `backend/src/domain/chat/tools/registry.py` — added `get_match_analysis` to
  `ALL_TOOL_SCHEMAS`, added `match_analytics_repository` param to
  `build_tool_registry`, registered with `widget_type="match_widget"`.
- `backend/src/api/v1/chat/routers/chat_router.py` — added
  `match_analytics_repository` to `_WIDGET_TYPE_TO_PART_CLASS` map and the
  `get_tool_registry` dependency chain.
- `backend/src/api/v1/chat/dtos/chat_dtos.py` — replaced `MatchWidgetPart`'s
  "Not implemented yet" docstring with the real one (mirrors
  `TeamWidgetPart`/`PlayerWidgetPart`).

**Key design notes not pre-decided in scope, resolved during implementation:**
- No jersey/squad-number column exists anywhere in the schema (`player` nor
  `match_lineup`) — `LineupPlayer.number` is a stable 1-based display ordinal
  by lineup order within each position group, not a real shirt number.
  Documented in `_match_analytics_builders.py`'s module docstring.
- No substitution-minute column — a starter's `minutes_played` is read as
  their off-minute, a used sub's `minutes_played` is read backwards from a
  90-minute match as their on-minute. Documented alongside.
- No formation/shape column — `shape` is derived as `DEF-MID-FWD` counts of
  the starting XI, a display-only stand-in.
- `Penalty Shootout Goal`/`Penalty Shootout Miss` event types have no clean
  `MatchEventKind` in the frontend's 4-kind union (`goal`/`card`/`var`/`sub`)
  — shootout goals map to `"goal"`, shootout misses are dropped from the
  timeline (same "no representation" treatment as substitutions).

**Verification commands run:**
- `python3 -m ruff check <all touched files>` → all checks passed.
- `python3 -m ruff format --check <all touched files>` → all already formatted.
- `python3 -m pytest` (full suite, with `DATABASE_URL`/etc. env vars pointed
  at the running `world-cup-ai-scout-postgres` docker container since no
  `.env` exists in this worktree) → `127 passed, 7 failed, 3 errors`; the 7
  failures + 3 errors are byte-identical to the pre-existing baseline
  (verified via a temporary WIP stash of all this change's files, then
  restored) — 0 regressions from this change.

## T7: frontend wiring (follow-up task)
- [x] Investigated whether the frontend needed new code to render
  `match_widget`. It didn't: `message-part.schema.ts`, `types.ts`,
  `message-part-renderer.tsx`, `use-chat-thread.ts`, and `side-panel.tsx`
  already handled `match_widget` end-to-end (widget + side panel), built
  forward-compat ahead of this tool's existence.
- [x] Verified field-for-field that the backend's `MatchAnalysis` Pydantic
  model (camelCase via alias generator) matches `matchSummarySchema` in
  `message-part.schema.ts` exactly — including string-typed `minute` /
  `homeValue` / `awayValue`, optional `venueLabel`/`detail`/`subOn`/`subOff`,
  and the `Position | "Subs used"` group-name union. A mismatch here would
  silently drop the widget in `parseMessageParts` with no visible error, so
  this check matters more than it looks.
- [x] Fixed two stale comments (`message-part-renderer.tsx`,
  `message-part.schema.ts`) that said match_widget was still
  forward-compat/unimplemented — now correctly listed alongside
  team_widget/player_widget as live.
- [ ] Live browser verification NOT done: the shared docker-compose stack
  (project name `world-cup-ai-scout`) was running mounted against a
  different worktree (`player-comparison-backend-e6ebc8`); user declined
  restarting it here to avoid interrupting that session. Verification relied
  on static schema comparison + the passing integration test suite instead.
