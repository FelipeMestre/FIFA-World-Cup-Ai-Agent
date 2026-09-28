# Player retirement heuristic + club display name fix

## Objective
1. Classify a Transfermarkt-sourced player as retired when they have no
   `real_player_season_stat` row in the last two known seasons, hide their
   current club when retired, and show a "Retired" badge in the frontend.
2. Wherever a Transfermarkt club's display name is shown, use
   `real_club.name`, not `real_club.club_code` (currently used for the
   `PlayerAnalysis.team_code` field in the Transfermarkt-fallback path).

## Why
User request, following up on the player-analysis-transfermarkt-fallback
work. Confirmed with the user: heuristic is deliberately simple (no season
stat row in the last two seasons = retired) and they're fine with occasional
misclassification.

## Scope / design decisions (confirmed with user or derived from real data)
- "Last two known seasons" is relative to the **dataset's own latest season**
  (`MAX(real_player_season_stat.season)`, currently `2025`), not wall-clock
  date — this is a synthetic/snapshot dataset, not live data. Verified
  against real rows: Gianluigi Buffon (latest season `2020`) and Andrés
  Iniesta (latest season `2017`) both correctly classify as retired against
  a dataset max of `2025`; Messi (latest season `2025`) does not.
- A player with **no** season-stat rows at all also classifies as retired
  (trivially "no row in the last two seasons").
- When retired: `PlayerClubProfile.current_club` is `None` (never show a
  stale club), and a new `PlayerClubProfile.is_retired: bool` field signals
  the frontend to render a "Retired" badge instead.
- This retirement computation applies to **both** career-loading paths in
  `player_club_career_repository.py` (`get_approved_career` and
  `get_career_by_real_player_id`) since both build the same
  `ApprovedClubCareer`/`PlayerClubProfile` shape — a World Cup player who
  has since retired from club football should also get the flag.
- `PlayerAnalysis.team_code` in the Transfermarkt-fallback path
  (`_build_transfermarkt_fallback_analysis` in `player_analytics_repository.py`)
  currently does its own separate `RealClubSchema` lookup by
  `real_player.current_club_id` and returns `club_code` — replace this
  entirely by deriving `team_code` from `career.profile.current_club` (the
  already-loaded, already-retirement-aware club name), removing the now
  redundant `_get_transfermarkt_team_code` method and its `RealClubSchema`
  import if unused elsewhere in that file.

## Constraints
- Follow existing layered architecture; keep changes inside
  `player_club_career_repository.py` / `player_analytics_repository.py` /
  `player_analysis.py` (backend) and the corresponding frontend
  types/components — no new abstractions beyond what this needs.
- Async repositories throughout. SQL-first for the max-season lookup.

## Tasks
- [x] T1: `backend/src/domain/player_analytics/model/player_analysis.py` —
      add `is_retired: bool` to `PlayerClubProfile`.
- [x] T2: `backend/src/infra/postgres/repositories/player_club_career_repository.py`
      — add a helper to fetch the dataset's latest known season year
      (`MAX(real_player_season_stat.season)`), a `_is_retired` predicate
      (no season row within the last two known seasons), and wire both into
      `_build_career` so `current_club` is nulled and `is_retired` set when
      retired.
- [x] T3: `backend/src/infra/postgres/repositories/player_analytics_repository.py`
      — replace `_get_transfermarkt_team_code`'s club-code lookup with
      `career.profile.current_club` (already retirement-aware); remove the
      dead method/import if nothing else in the file uses `RealClubSchema`.
- [x] T4: Frontend — read `frontend/src/features/chat/types.ts` (`PlayerClubProfile`),
      `player-club-profile.tsx`, `player-club-format.ts`, `panel-player.tsx`,
      `widget-player.tsx`, and `sample-data/player.ts` to find the exact
      existing pattern for rendering club-profile facts/badges. Add
      `isRetired: boolean` to the `PlayerClubProfile` type and render a
      "Retired" badge (reuse whatever badge/chip primitive the codebase
      already uses elsewhere in this widget — don't invent a new one) in
      whichever of `widget-player.tsx`/`panel-player.tsx`/
      `player-club-profile.tsx` already renders club-profile facts, matching
      existing component conventions (shadcn `Badge` per this project's
      Tailwind rules if one isn't already in use here). Also add a sample
      retired-player fixture case to `sample-data/player.ts` if that file is
      exercised by a Storybook-style preview or test, so the badge is
      visually checkable.
- [x] T5: verification — backend: TDD (RED test for `_is_retired`/club-name
      behavior first, using the real Buffon/Iniesta-style fixture data
      pattern the existing `test_player_analytics_repository.py` /
      `test_player_club_career_repository.py`-style tests already use, then
      GREEN), ruff clean, full pytest suite compared against baseline (see
      the sibling task files in this same `odd/tasks/` directory for the
      established stash-and-compare pattern — **but see the important
      warning below**). Frontend: run the relevant unit tests
      (`player-club-format.test.ts`, `message-part-schema.test.ts`) and any
      type-check/lint the project uses.

## IMPORTANT — do not repeat the earlier data-loss incident
An earlier session's baseline-comparison step ran `alembic upgrade heads` /
downgrade cycles against the **shared** `world-cup-ai-scout-postgres` docker
container (used by multiple concurrent worktree sessions on this host) and
this **dropped and emptied the `conversation` table's real data** as a side
effect of a downgrade run by some session against that shared container.
For this task:
- Do NOT run any `alembic downgrade` against the shared
  `world-cup-ai-scout-postgres` container.
- If a baseline/regression comparison is needed, prefer comparing against
  git history (e.g. `git stash` your own new files only, rerun just the
  directly affected test files, restore) rather than migrating the shared
  database up/down. If full-suite baseline comparison is genuinely necessary,
  ask the user first before running any migration command against that
  container.

## Acceptance criteria
- [x] Buffon/Iniesta-style fixture (or the real dev-DB rows, read-only) shows
  `is_retired=True`, `current_club=None`.
- [x] Messi-style fixture (recent season row) shows `is_retired=False` with
  their real current club **name** (not code).
- [x] `team_code` in the Transfermarkt-fallback path shows the club's name,
  not its short code, and is empty/placeholder when retired or clubless.
- [x] Frontend renders a "Retired" badge when `isRetired` is true, and the
  current-club line does not render (or shows nothing) in that case.
- [x] ruff clean; frontend lint/tests clean; no regressions in directly
  affected backend tests (full-suite baseline comparison only if the shared
  DB isn't put at risk — see warning above). Full-suite comparison was
  **not** run — see evidence below for why and what was run instead.

## Progress / evidence

**Files modified:**
- `backend/src/domain/player_analytics/model/player_analysis.py` (T1) —
  added `is_retired: bool` (required) to `PlayerClubProfile`.
- `backend/src/infra/postgres/repositories/player_club_career_repository.py`
  (T2) — added `_is_retired(career_seasons, latest_known_year)` (pure
  predicate: `max(_season_start_year(s.season) for s in career_seasons,
  default=0) < latest_known_year - 1`) and `_load_latest_known_season_year`
  (`SELECT MAX(real_player_season_stat.season)`, parsed via the existing
  `_season_start_year`). Wired both into `_build_career` (the single funnel
  both `get_approved_career` and `get_career_by_real_player_id` already
  went through): `current_club=None if is_retired else club_name`,
  `is_retired=is_retired`.
- `backend/src/infra/postgres/repositories/player_analytics_repository.py`
  (T3) — `_build_transfermarkt_fallback_analysis` now derives `team_code`
  from `career.profile.current_club or "???"` (the call to
  `get_career_by_real_player_id` was already ahead of the old team-code
  lookup, so no reordering was needed — just replacing the lookup itself).
  Removed the now-dead `_get_transfermarkt_team_code` method and its
  `RealClubSchema` import (confirmed via `rg` that nothing else in this
  file referenced `RealClubSchema`).
- `backend/tests/integration/infra/test_player_analytics_repository.py`
  (T5) — added
  `test_get_player_analysis_flags_retired_transfermarkt_player` (TDD:
  written first, confirmed RED via a pydantic `ValidationError` on the
  missing `isRetired` field, then GREEN after T1-T3). Also updated the
  existing `test_get_player_analysis_falls_back_to_transfermarkt_when_no_world_cup_row`
  assertion from `analysis.team_code == "BVB"` to `== "Borussia Dortmund"`
  (T3's behavior change directly affects that assertion).
- Frontend `frontend/src/features/chat/types.ts` (T4) — added
  `isRetired: boolean` to `PlayerClubProfile`.
- `frontend/src/features/chat/schemas/message-part.schema.ts` (T4) — added
  `isRetired: z.boolean().default(false)` to the inline `clubProfile` zod
  shape (defaulted rather than required, so a widget stored before this
  field existed still validates instead of failing the whole message part).
- `frontend/src/features/chat/components/player-club-profile.tsx` (T4) —
  renders `<Badge variant="outline">Retired</Badge>` next to the existing
  "Club profile" heading when `profile.isRetired` is true; also changed the
  early-return guard from `facts.length === 0` to
  `facts.length === 0 && !profile.isRetired` so the badge still shows even
  when a retired player has no other visible facts (e.g. a Transfermarkt
  row with only a name). "Current club" already disappears on its own: the
  backend nulls it and `clubProfileFacts` already filters out any fact
  whose value is `null` — no extra suppression logic was needed on the
  frontend.
- `frontend/src/features/chat/sample-data/player.ts` (T4) — added
  `isRetired: false` to both existing samples' `clubProfile` and a new
  `samplePlayerRetired` (Gianluigi Buffon, goalkeeper, `currentClub: null`,
  `isRetired: true`) fixture for visual/test verification.
- `frontend/tests/unit/features/chat/player-club-format.test.ts` — added
  `isRetired: false` to its local `PlayerClubProfile` fixture (`tsc`
  flagged this as a missing required property after T4's type change).

**Design decisions resolved during implementation (not fully pre-specified):**
- **Badge component and placement**: used the existing shadcn `Badge`
  (`frontend/src/components/ui/badge.tsx`, already used elsewhere in the
  codebase, e.g. `identity-link-review-card.tsx`, `stage-progress.tsx`) with
  `variant="outline"` (neutral, not the default primary-colored variant,
  since "retired" is informational, not a success/error/warning state).
  Placed it inline next to the "Club profile" heading inside the single
  shared `PlayerClubProfileFacts` component (`player-club-profile.tsx`)
  rather than duplicating it into both `widget-player.tsx` and
  `panel-player.tsx` — that component is already the one shared render
  point both call, so the badge shows in both the compact widget and the
  full side panel with one change.
- **Suppressing the current-club line**: no explicit frontend suppression
  logic was added. `PlayerClubProfile.current_club` is already `None` at
  the source (T2's `_build_career` change) for a retired player, and
  `clubProfileFacts` (`player-club-format.ts`) already `flatMap`s away any
  fact whose value is `null` — so the "Current club" row disappears as a
  direct consequence of the backend change, with no new frontend branch
  needed beyond the badge itself.

**Verification commands run:**
- Backend TDD: `python3 -m pytest tests/integration/infra/test_player_analytics_repository.py -k "transfermarkt or retired" -q`
  → RED first (`pydantic_core._pydantic_core.ValidationError: 1 validation
  error for PlayerClubProfile / isRetired / Field required`), then GREEN
  after implementing T1-T3.
- `python3 -m pytest tests/integration/infra/test_player_analytics_repository.py -q`
  → 15 passed, 1 failed. The 1 failure
  (`test_get_player_analysis_resolves_accented_query_via_unaccent`) is the
  same pre-existing, unrelated flake the sibling
  `player-analysis-transfermarkt-fallback.md` task already documented: the
  shared dev DB has a real, non-synthetic "Kylian Mbappe" `player` row (id
  842) alongside this test's own synthetic one, and the exact-match query's
  `.first()` non-deterministically returns either. Not touched by this
  change.
- `python3 -m ruff check` + `python3 -m ruff format --check` on every
  backend file touched (`player_analysis.py`,
  `player_club_career_repository.py`, `player_analytics_repository.py`,
  `test_player_analytics_repository.py`) → all clean.
- Frontend: `npx vitest run tests/unit/features/chat/player-club-format.test.ts tests/unit/features/chat/message-part-schema.test.ts`
  → 2 files, 11 tests, all passed.
- `npx eslint` on every frontend file touched (`types.ts`,
  `message-part.schema.ts`, `player-club-profile.tsx`, `sample-data/player.ts`)
  → no issues.
- `npx tsc --noEmit -p .` (project has no dedicated typecheck script) →
  pre-existing, unrelated errors only (missing `react-markdown`/`remark-gfm`
  type declarations, a `venueLabel` null/undefined mismatch in
  `apply-live-event.ts`/`parse-message-parts.ts`, implicit-`any` bindings in
  `assistant-markdown.tsx`, two `use-chat-thread.test.tsx` errors) — none in
  files this task touched. One error this task's own type change surfaced
  (`player-club-format.test.ts` missing `isRetired`) was fixed and
  re-verified gone.

**Explicitly skipped, and why:**
- **Full-suite pytest baseline comparison** (mentioned in T5 and the
  acceptance criteria) was **not** run. Per this task file's own data-loss
  warning, an earlier session's `alembic upgrade`/`downgrade` cycling
  against the shared `world-cup-ai-scout-postgres` container previously
  wiped the `conversation` table, and the instructions for this run
  explicitly said to stop and ask before running any migration against that
  container rather than doing it unprompted. Instead: ran the directly
  affected test file in isolation (`test_player_analytics_repository.py`,
  see above) and confirmed only the one pre-existing, already-documented
  flake. No migration command was run.
- Confirmed the real dev-DB read-only facts this task's design decisions
  cite, via `docker exec world-cup-ai-scout-postgres psql -U
  world_cup_ai_scout -d world_cup_ai_scout -c "..."` (read-only `SELECT`
  only, no migrations): dataset `MAX(season)` is `2025`; Buffon
  (`player_id=5023`) latest season `2020`; Iniesta (`player_id=7600`)
  latest season `2017`; Messi (`player_id=28003`) latest season `2025`.
  None of these three real players have an approved (or any)
  `player_identity_link` row, so they resolve through the
  Transfermarkt-fallback path rather than `get_approved_career` — the new
  unit test instead exercises the retirement predicate with synthetic
  fixtures scoped to their own transaction (matching this file's existing
  pattern), which is deterministic and doesn't depend on the shared
  dataset's own season data drifting over time.
