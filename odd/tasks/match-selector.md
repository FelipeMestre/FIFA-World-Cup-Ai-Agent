# Match selector

## Objective
A "Match" chip on the chat composer: search matches by team name text (e.g.
"brazil" -> every Brazil match), select one. The selected match is (a) fed to
the agent as a *directive* instruction that it must call `get_match_analysis`
with that match's exact team names/date, and (b) recorded as JSON `metadata`
on the persisted user message, so the frontend can render a small badge on
that message's bubble showing which match was selected.

## Decisions
- Feeds the agent (confirmed): the selected match forces `get_match_analysis`
  tool use, not just passive "take into account" phrasing -- an earlier
  attempt at passive context phrasing (for the now-reverted player/team
  selectors) caused the model to skip a matching tool call. This time the
  injected message is an imperative instruction naming the exact tool and
  arguments to call, not a fact statement.
- Single-select (unlike the earlier player(2)/team(2) selectors) -- one match
  per message.
- No pagination on the search endpoint -- the whole tournament is ~100
  matches, filtered results will always be small.
- Metadata is server-resolved (not client-echoed) so the badge label always
  reflects real match data, not a stale client-side label.

## Scope
- Backend: `search` on the match repository (join to national_team for
  names); `GET /matches/search`; a `metadata` JSONB column on `chat_message`
  (new Alembic migration) threaded through persistence, replay DTO, and the
  live SSE `user_message` event; the `context`/`SendMessageRequest` plumbing
  from the earlier (reverted) feature rebuilt from scratch, this time only
  for `match_id`; `ChatService.send_message` resolves it and injects the
  directive instruction.
- Frontend: `entity-chip-selector.tsx` recreated (deleted in the full
  revert) for a single-select Match chip; `search-matches.ts` + proxy route;
  `metadata` threaded through optimistic send, live events, and history
  replay; a badge on `UserBubble` in `chat-bubble.tsx`.

## Tasks

### Backend
- [x] T1: `search(query)` on `MatchRepositoryInterface`/impl -- join to
  `NationalTeamSchema` (home + away), `ilike`+`unaccent` on either team's
  name/fifa_code (mirror `_resolve_team` in `team_analytics_repository.py`),
  order by `match.date` ascending, no limit/offset.
- [x] T2: `MatchSearchResultDto` (`id, date, home_team_id, home_team_name,
  away_team_id, away_team_name, home_score, away_score, status`) and
  `GET /matches/search?q=` in `match_router.py` (`q: Query(min_length=2)`).
- [x] T3: New Alembic migration adding a nullable JSONB `metadata` column to
  `chat_message` (mirror the style of existing additive migrations in
  `backend/migrations/versions/`). `ChatMessageSchema` gets the column,
  `ChatMessage` domain model gets `metadata: dict | None = None`,
  `append_message(...)` gets an optional `metadata` param threaded into the
  insert and `_to_domain`.
- [x] T4: `ConversationMessageDto` gets `metadata: dict | None = None`
  (threaded through wherever it's built from a persisted message); the SSE
  `user_message` event payload (`serialize_user_message_event` in
  `chat_streams.py`) gets the same field.
- [x] T5: Recreate `MessageContextDto` (`match_id: int | None = None`) and
  `SendMessageRequest.context: MessageContextDto | None = None` in
  `conversation_dtos.py` (this was fully removed in an earlier revert).
- [x] T6: In `conversation_router.send_message`: when `context.match_id` is
  present, resolve the match + both team names (request-scoped
  `MatchRepositoryDep`/`NationalTeamRepositoryDep`), build
  `{"match_selector": {"match_id": ..., "label": "<home> vs <away> —
  <date>"}}`, pass as `metadata` to `persist_user_message`. Thread
  `payload.context.model_dump() if payload.context else None` through
  `enqueue_chat_reply` -> `generate_chat_reply_task` -> `ChatService.send_message`
  (rebuild this 3-hop chain from scratch -- also fully reverted).
- [x] T7: `ChatService` gets new constructor deps `match_repo`,
  `national_team_repo`. `send_message`'s `context` resolves the match the
  same way, and injects a **directive** system message ("You MUST call
  get_match_analysis with home_team_name=..., away_team_name=..., date=...
  before answering") -- not a passive fact statement. Wire the new deps
  through `chat_service_factory.py` and `chat_tasks.py`.

### Frontend
- [x] T8: `frontend/src/app/api/matches/search/route.ts` proxy route
  (mirror the players/teams search route pattern used before).
- [x] T9: `search-matches.ts` fetcher.
- [x] T10: Recreate `entity-chip-selector.tsx` (generic chip + search
  dropdown, stays open until `maxSelected` reached) -- deleted in the full
  revert of the earlier feature.
- [x] T11: Wire a single-select Match chip into `home-shell.tsx`'s composer
  (`selectedMatch`, cap 1), forward `matchId` into `submit`/`sendMessage`.
- [x] T12: `ChatMessage.metadata` type; thread it through the optimistic
  send path, `apply-live-event.ts`'s live `user_message` handling, and
  `get-conversation-messages.ts`'s replay parsing.
- [x] T13: Badge on `UserBubble` (`chat-bubble.tsx`) in the bottom-left
  corner of the message, shown when `metadata.matchSelector` is present.

## Verification
- Backend: `ruff check --fix` + `ruff format` on touched files; confirm the
  migration applies (`alembic upgrade head` if a local/dev DB is reachable
  in this environment, otherwise note it as unverified).
- Frontend: `eslint`/`tsc --noEmit` on touched files, diffed against the
  pre-existing baseline errors already known from earlier sessions.
