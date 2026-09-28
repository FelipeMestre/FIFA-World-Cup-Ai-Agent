# Player analysis — Transfermarkt fallback for non-World-Cup players

## Objective
`get_player_analysis` currently only resolves players against the World Cup
`player` table. When a name isn't found there, fall back to the
Transfermarkt-sourced `real_player` table and return a career-stats-totals
version of `PlayerAnalysis` instead of a "not found" error.

## Why
User request: players who never played in a World Cup (e.g. current club-only
players) have no `player`/`player_stat` row but do exist in `real_player` /
`real_player_season_stat`. The agent tool should still answer for them.

## Scope / design decisions (confirmed with user)
- No visible "data source" badge/indicator in the frontend. The fallback
  reuses the exact same `PlayerAnalysis`/`PlayerSummary` shape and layout —
  no new fields, no UI distinction.
- `full_breakdown` in the fallback case holds **summed career totals**
  (appearances, goals, assists, yellow cards, red cards, minutes) instead of
  match-level stats. `percentile` is `null` for every row (no World Cup peer
  population exists for Transfermarkt-only players).
- `per_ninety_vs_position_average` is an empty list in the fallback case (no
  peer average exists to benchmark against).
- `club_profile`, `transfers`, `career_seasons` are populated directly from
  `real_player` / `real_transfer` / `real_player_season_stat` for the matched
  `real_player_id`, bypassing the `player_identity_link` APPROVED-status gate
  that `get_approved_career` requires (that gate is for enrichment of an
  *already-resolved* World Cup player; the fallback has no World Cup player
  at all).
- Fallback search reuses `RealPlayerRepositoryInterface.search`; add
  unaccented ILIKE + exact-match-first tiering to it so fallback search has
  the same diacritic tolerance as the primary `_resolve_player` path.

## Constraints
- Keep the fallback branch inside the repository layer only —
  `get_player_analysis.py` (the tool) needs no branching, per existing
  architecture (repository owns "player not found" resolution entirely).
- SQL-first aggregation for the totals sum (AGENTS.md).
- Async repositories throughout.
- No new abstractions beyond what this needs.

## Tasks
- [x] T1: `real_player_repository.py` — add unaccented ILIKE + exact-tier to
      `search` (mirror `_resolve_player`'s two-tier approach).
- [x] T2: `player_club_career_repository.py` / interface — new method to load
      club profile + transfers + season stats directly by `real_player_id`
      (no identity-link join, no APPROVED filter), returning the existing
      `ApprovedClubCareer`-shaped data (rename/generalize if the "Approved"
      naming no longer fits).
- [x] T3: `player_analytics_repository.py` — when `_resolve_player` finds no
      World Cup row (or finds one with no stat row), fall back to
      `RealPlayerRepositoryInterface.search` (limit 1) and, on a hit, build a
      `PlayerAnalysis` from the T2 career data: totals-based
      `full_breakdown` (percentile always `null`), empty
      `per_ninety_vs_position_average`, `position` mapped from
      `real_player.position`, `appearances`/`minutes` summed from season
      stats. Inject `RealPlayerRepositoryInterface` into the repository's
      factory.
- [x] T4: update `get_player_analysis.py`'s tool-schema description to
      mention the Transfermarkt fallback.
- [x] T5: verification — ruff clean, full pytest suite, baseline comparison
      for regressions.

## TDD mode
Strict TDD Mode enabled (user's CLAUDE.md). Runner: `pytest`
(`asyncio_mode = "auto"`). Write the fallback repository test first against
`_SqlAlchemyPlayerAnalyticsRepository.get_player_analysis` for a
Transfermarkt-only name, confirm RED, then implement to GREEN.

## Acceptance criteria
- [x] A player name present only in `real_player` (not in `player`) returns a
  populated `PlayerAnalysis` instead of the "not found" error.
- [x] `full_breakdown` rows show career totals with `percentile: null`.
- [x] `per_ninety_vs_position_average` is `[]` for fallback players.
- [x] Existing World Cup player resolution behavior is unchanged.
- [x] Frontend renders the fallback response with no code changes needed
  (same `PlayerAnalysis`/`PlayerSummary` shape) — no frontend files touched.
- [x] ruff clean; no regressions vs. baseline test run (verified via
  stash-and-compare, see evidence below).

## Progress / evidence

**Files created:**
- `backend/src/infra/postgres/repositories/_transfermarkt_player_view.py`
  (85 lines) — pure career-totals breakdown builders for the fallback path
  (`build_full_breakdown`, `build_chips`, `discipline_label`,
  `total_appearances`, `total_minutes`), mirroring
  `_player_analysis_view.py`'s role for the World Cup path but with every
  row's `percentile` hardcoded `None` (no peer population exists).

**Files modified:**
- `backend/src/infra/postgres/repositories/real_player_repository.py` (T1)
  — `search` now does the same two-tier unaccented-ILIKE (exact match
  first, substring fallback) as `_resolve_player`. Added
  `build_real_player_repository(session)` plain builder (mirrors
  `build_player_club_career_repository`) so
  `player_analytics_repository.py` can self-wire this dependency without
  new FastAPI-level wiring.
- `backend/src/infra/postgres/interfaces/player_club_career_repository_interface.py`
  + `backend/src/infra/postgres/repositories/player_club_career_repository.py`
  (T2) — added `get_career_by_real_player_id(real_player_id)`, which loads
  the same `ApprovedClubCareer`-shaped data as `get_approved_career` but
  keyed directly off a known `real_player_id`, bypassing the
  `player_identity_link`/APPROVED join. Refactored the shared
  profile-building code into `_build_career` to avoid duplicating it
  between the two entry points. Kept the `ApprovedClubCareer` dataclass
  name unchanged rather than renaming it — see "design decisions resolved
  during implementation" below.
- `backend/src/infra/postgres/repositories/player_analytics_repository.py`
  (T3) — `get_player_analysis` now falls back to
  `_build_transfermarkt_fallback_analysis` whenever `_resolve_player`
  finds nothing, or finds a `player` row with no `player_stat` row. Split
  the previous single method into `_build_world_cup_analysis` (unchanged
  behavior, just extracted) and the new fallback builder. Constructor now
  also takes an injectable `real_player_repository` parameter, defaulting
  to `build_real_player_repository(session)`.
- `backend/src/infra/postgres/interfaces/player_analytics_repository_interface.py`
  — docstring updated to document the fallback behavior.
- `backend/src/infra/postgres/repositories/_player_stat_helpers.py` — added
  `"A"` (Transfermarkt's `"Attack"`) to `_POSITION_BY_FIRST_LETTER` so
  `normalize_position` maps it to `FWD`; **found and fixed a latent bug**
  while doing this: `_FIRST_LETTER_BY_POSITION` was derived by reversing
  the forward map, which would have silently made `first_letter_for_position
  ("FWD")` return `"A"` instead of `"F"` once a second key mapped to `FWD`
  -- breaking `_get_position_peers`'s World-Cup-only `player_stat.position
  ILIKE 'F%'` peer query for every forward. Fixed by making
  `_FIRST_LETTER_BY_POSITION` an explicit literal instead of a derived
  reversal.
- `backend/src/domain/chat/tools/get_player_analysis.py` (T4) — schema
  description now mentions the Transfermarkt career-totals fallback and
  that it carries no percentile ranking.
- `backend/tests/integration/infra/test_player_analytics_repository.py` —
  added `test_get_player_analysis_falls_back_to_transfermarkt_when_no_world_cup_row`
  (TDD: written first, confirmed RED via
  `assert None is not None` against the un-implemented fallback, then
  implemented to GREEN).

**Design decisions resolved during implementation (not pre-specified in scope):**
- **`ApprovedClubCareer` naming**: kept as-is rather than renamed/generalized.
  It's imported by `player_analysis.py` (the shared read model) and referenced
  across both the approved-link and now the direct-by-id path; renaming it
  would touch unrelated call sites for a cosmetic gain. Documented the
  broadened meaning in the new interface method's docstring instead.
- **`position` mapping (point 5 in the task brief)**: confirmed via existing
  integration-test fixtures (`test_transfermarkt_detail_upsert_constraints.py`,
  `test_real_player_repository.py`, `test_player_analytics_repository.py`)
  that `real_player.position` holds Transfermarkt's own words --
  `"Attack"`, `"Defender"`, `"Midfield"`, `"Goalkeeper"` -- not the World
  Cup schema's 2-letter codes. Three of those four already map correctly
  through the existing first-letter `normalize_position`, but `"Attack"`
  starts with `"A"`, which had no entry and would have silently fallen
  back to `"MID"`. Added `"A" -> "FWD"` to the shared map (safe: no World
  Cup position code starts with `"A"`) rather than writing a separate
  Transfermarkt-only normalizer function.
- **`team_code` (point 7)**: `RealClubSchema` already has a `club_code`
  column (Transfermarkt's own short club code, e.g. `"BVB"`, `"PSG"`) --
  used that directly via `current_club_id`, with `"???"` when the player
  has no current club or the club row is missing. No new column needed.
- **`scope_label`/`tier_label`/`tier_segments`/`discipline_label`/`chips`/
  `footer_caption` (point 8)**: chose neutral, non-tiering values rather
  than forcing WC-style percentile language onto peer-less totals:
  `scope_label="Club career · totals"`, `tier_label="Club career"`,
  `tier_segments=0` (no filled meter -- there's no percentile-based tier to
  fill it with). `discipline_label` and `chips` are still computed, just
  from summed career totals instead of a single tournament's stat row,
  since both are meaningful without a peer population (discipline is a
  card-count read on the player themselves, not a percentile rank).
- **Fixed a latent position-peer-query bug** while extending
  `_player_stat_helpers.py` (see file list above) -- not something the
  task asked for, but adding a second key mapping to `"FWD"` would have
  silently broken `_get_position_peers` for every forward if left as a
  derived reversal.

**Verification commands run:**
- `python3 -m ruff check <all touched .py files>` -> all checks passed.
- `python3 -m ruff format --check <all touched .py files>` -> one file
  (`real_player_repository.py`) needed reformatting after the edit; ran
  `ruff format` on it, then re-confirmed clean.
- TDD: `python3 -m pytest tests/integration/infra/test_player_analytics_repository.py -k transfermarkt`
  -> RED (`assert None is not None`) before implementation, GREEN after.
- `python3 -m pytest` (full suite) -- **the shared dev Postgres container
  (`world-cup-ai-scout-postgres`, port 55432) this worktree's `.env` points
  at is actively being started/stopped and migrated/downgraded by other
  concurrent sessions/worktrees during this task** (confirmed: found it
  fully stopped at the start of this task, and its migration head reverted
  from fully-migrated back down to `db800dd3ee39` -- and once even further,
  dropping `national_team` entirely -- between consecutive `alembic
  current` checks with no action from this session in between). This is
  the same instability the sibling task's evidence section
  (`match-analysis-widget-backend.md`) already flagged for this shared
  container. To get an honest regression comparison despite that churn:
  ran `alembic upgrade heads` immediately before each pytest run, then
  `python3 -m pytest -q` with my changes in place, then `git stash push -u`
  (tagged, captured its SHA, restored via `git stash apply <sha>` then
  dropped by re-derived ref -- never a bare `stash pop`, per this session's
  git-safety rules) + `alembic upgrade heads` again + the same `pytest -q`
  run for baseline, then restored my changes the same way. Result: **the
  sorted `FAILED` test list was byte-identical between baseline and this
  change -- 13 failures, 0 regressions.** All 13 are pre-existing and
  unrelated to this change (two migration-roundtrip tests that leave the
  shared schema mid-migration for the rest of that same pytest process --
  `test_ingestion_repository.py::test_migration_roundtrip` and
  `test_transfermarkt_detail_upsert_constraints.py::test_migration_roundtrip`
  -- cascade into `real_player_repository` search tests and
  `ingestion_repository` row-count tests failing later in the same run;
  `test_tool_call_executor.py`'s three widget-event tests are unrelated to
  player analytics). Additionally, `test_player_analytics_repository.py`'s
  own pre-existing `test_get_player_analysis_resolves_accented_query_via_unaccent`
  fails on both baseline and this change for an unrelated reason: the
  shared dev DB already has a real, non-synthetic "Kylian Mbappe" `player`
  row (id 842) alongside this fixture's own synthetic one (id 990604), and
  the exact-match query's `.first()` non-deterministically returns either
  -- not something this change touches or introduces.
- Running the full suite in isolation right after a fresh `alembic upgrade
  heads` (to sidestep the container churn) and filtering to just this
  change's own test files: `test_player_analytics_repository.py` ->
  14 passed, 1 failed (only the pre-existing accented-Mbappe ambiguity
  above); the new fallback test passes cleanly on its own.
