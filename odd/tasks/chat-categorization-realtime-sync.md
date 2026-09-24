# Chat categorization + SSE realtime migration

## Objective
Auto-categorize a new chat (LLM-generated title + icon) right after creation, and
replace the WebSocket transport with SSE (receive) + POST (send) so the update
reaches every device/tab connected to the same account, not just the one viewing
that conversation.

## Problem / why
- Today's realtime channel (`live_router.py`) is a per-conversation WebSocket.
  It requires a bespoke ticket-minting auth dance (WS can't carry the httpOnly
  session cookie) and only reaches clients currently watching that one
  conversation — there's no per-user fanout, so a sidebar on another device
  never learns about a generated title/icon.
- Decision (this session, 2026-09-24): migrate both directions to plain HTTP —
  `POST` to send a message, SSE (`GET`, `text/event-stream`) to receive both
  chat-turn events and user-scoped events (conversation categorized). Chosen
  because SSE rides ordinary HTTP through any proxy/LB without WS-specific
  config, drops the ticket system (cookie auth works automatically through a
  Next.js proxy route), and gives native reconnect/resume via `Last-Event-ID`
  matching the existing Redis Stream cursor model.

## Scope
- Backend: DB migration (`icon`, `title_is_generated` on `conversation`),
  domain model + schema + repository changes, new `categorize_conversation_task`
  Arq job, new `POST /conversations/{id}/messages` send endpoint, new merged
  SSE endpoint (per-conversation turn stream + per-user event stream via
  multi-key `XREAD`), removal of `live_router.py`'s WS route + ticket endpoint.
- Frontend: new SSE-consuming hook (replaces `conversation-live.ts`'s WS
  client), new POST-based send function, Next.js SSE proxy route (cookie auth,
  streams backend response through), sidebar applies live
  `conversation_updated` events regardless of which conversation is open.
- Out of scope: no cancel-turn feature (previously decided against); no change
  to `chat_message`/`chat_message_widget` schema; no change to the OpenRouter
  client itself.

## Constraints
- TDD mode: **enabled** (source: user's global CLAUDE.md "Strict TDD Mode:
  enabled"). Runner: `pytest` (backend/pyproject.toml), async client per
  AGENTS.md (`httpx.AsyncClient` + `ASGITransport`, `dependency_overrides`).
  RED before implementation, then GREEN, then REFACTOR for every task with
  behavior to test.
- Never clobber a manually-renamed title: `update_category` must no-op the
  title write when `title_is_generated=False`.
- `XREAD` supports multiple stream keys in one blocking call — use this for
  the merged SSE loop instead of two separate read loops.
- Delivery: feature-branch-chain — work-unit commits on the current branch
  (`claude/chat-categorization-realtime-sync-b5bee9`), PR opened when the user
  asks. Forecast is well over the ~400-line advisory heuristic (backend +
  frontend protocol swap); that's expected for this task, not a reason to
  split artificially.

## Tasks

- [x] **T1 — DB + model + repository foundation** (route: delegated writer —
  touches migration, domain model, schema, repository, interface: 5 files;
  commit 357dffa)
  - Alembic migration: add `icon: str` (nullable, enum-constrained at app
    level) and `title_is_generated: bool default true` to `conversation`.
  - `Conversation` dataclass: add both fields.
  - `ConversationSchema`: add both columns.
  - `ConversationRepositoryInterface` + impl: `update_category(conversation_id,
    title, icon)` (respects `title_is_generated` guard); `update_title` sets
    `title_is_generated=False`; `get_or_create` returns `(conversation,
    created: bool)`.
  - Tests: repository test for the guard behavior, `get_or_create` created-flag.

- [x] **T2 — Categorization Arq job** (route: delegated writer — job file +
  worker registration + new stream helpers: 3 files; commit 08881d4)
  - `categorize_conversation_task(ctx, conversation_id, user_id, first_message)`
    in `chat_tasks.py`: calls `get_openrouter_client().create_chat_completion`
    directly (no `ToolCallExecutor`), single aggregated JSON result
    `{title, icon}` from a fixed icon enum, persists via `update_category`,
    `XADD`s `ConversationCategorizedEvent` to new `user:events:{user_id}`
    stream (helper `user_events_key`).
  - Register in `worker.py` via `func(categorize_conversation_task,
    timeout=...)`.
  - Enqueue call site added where conversation `created=True` is observed.
  - Tests: job persists correctly, guard respected, stream entry shape.

- [x] **T3 — POST send endpoint, added alongside WS (not replacing yet)**
  (route: delegated writer — new router + service wiring: 2-3 files)
  - `POST /conversations/{id}/messages`: ownership check, `chat_service
    .start_turn` (categorization enqueue already happens inside it, per T2 —
    nothing more to do here for that), reserve turn (`SET NX EX`), persist
    user message, `XADD` `UserMessageEvent`, `enqueue_chat_reply`. Returns
    202 ack.
  - `live_router.py`'s WS route is left untouched and still functional —
    both send paths work in parallel until T4 deletes the WS route once the
    SSE endpoint (T4) is live and the frontend (T5/T6) has migrated.
  - Tests: 202 ack shape, turn-in-progress 409 conflict preserved.

- [x] **T4 — Merged SSE endpoint, remove WS** (route: delegated writer —
  new router + removal of old one: 2-3 files)
  - `GET /conversations/{id}/events`: `StreamingResponse`
    (`text/event-stream`), multi-key `XREAD BLOCK` over
    `chat:turn-stream:{id}` and `user:events:{user_id}`, resumes from
    `Last-Event-ID` header, `event:` field distinguishes `turn` vs
    `conversation_updated`.
  - Remove `live_router.py`'s WS route and `POST /chat/ws-tickets` (ticket
    system no longer needed — cookie auth via Next.js proxy).
  - Tests: resume-from-cursor behavior, both stream types forwarded with
    correct `event:` tagging.

- [x] **T5 — Frontend: full SSE+POST migration** (route: delegated writer —
  merged with what was separately T6, since send/receive are wired together
  in the same hook and splitting them across two agents touching the same
  files back-to-back is more error-prone than one coherent pass; ~8-10 files)
  - New `conversation-events.ts` (replaces `conversation-live.ts`):
    `EventSource`-based, native `Last-Event-ID` resume (delete the hand-rolled
    reconnect/pending-queue/`cursorsRef`/`isCursorAtOrBefore` dedup — all
    superseded by native SSE resume).
  - New `send-message.ts`: plain POST, replacing the WS `send` frame.
  - New streaming SSE proxy route + new POST proxy route (`proxyBackendJson`
    fits the latter directly). Delete `live-ticket/route.ts`.
  - `use-chat-thread.ts`: SSE for receive, POST for send; a POST failure
    (403/409) replaces the old `rejected` WS event — caught directly, not
    awaited as a stream event.
  - `use-conversation-list.ts`: new `applyConversationUpdate` patches a row's
    title/icon in place from a live `conversation_updated` event, wired
    through `home-shell.tsx` the same way `onConversationCreated` already is.
  - `ConversationSummary`/zod schema: add `icon`. Sidebar row: render it via
    a category→lucide-icon lookup (the backend's `icon` is a semantic
    category key — general/player/team/match/tactics/transfer/injury/
    stats/history — not a literal icon name).
  - Note (told to the user directly, not a blocker): a device with the
    sidebar open but no conversation selected has no SSE connection at all,
    same as the old WS design already had — "every connected device" means
    every device with *some* conversation open, not literally always-on.

## Acceptance criteria
- Sending a message works end-to-end via POST + SSE turn events (parity with
  today's WS behavior, including `is_generating` sidebar spinner).
- A newly created conversation gets an LLM-generated title + icon, visible on
  every open device/tab for that account without a manual reload.
- Manually renaming a conversation before categorization resolves is never
  overwritten by the categorization result.
- No WebSocket code paths remain for this feature.

## Progress
- 2026-09-24: Extra fix before T5 — `ConversationSummaryDto` (`GET
  /conversations`) never actually exposed `icon` (T1's column existed but
  was never serialized); a reload would silently drop what a live
  `conversation_updated` event just delivered. Fixed directly (2-line,
  mechanical), commit 6d9cfb8.
- 2026-09-24: T5 delegated (merged former T5+T6 into one frontend task — see
  the task entry above for why). Also flagged to the user: the merged SSE
  endpoint is per-conversation-scoped (`GET /conversations/{id}/events`), so
  a device with the sidebar open but no conversation selected has no live
  connection at all — same limit the old WS design already had. "Every
  connected device" means every device with *some* conversation open, not a
  standalone always-on per-user channel.
- 2026-09-24: Task file created. Starting T1.
- 2026-09-24: T1 done, commit 357dffa. RED→GREEN verified (14 passed in
  `test_conversation_repository.py`), migration applied + reversed + reapplied
  cleanly against real Postgres. Spot-checked the `update_category` guard and
  `update_title` diff directly — correct. `ruff` clean. A pre-existing,
  unrelated systemic bug was found (9 other test files' seed-user fixtures hit
  an `asyncpg` `AmbiguousParameterError` on a reused `:email` param in
  different type contexts) — flagged as a separate background task, not fixed
  here (out of T1's scope). Docker `postgres`/`redis` compose services were
  started locally by the writer agent for the integration tests and are still
  running.
- 2026-09-24: T2 (categorization Arq job) delegated. Enqueue call site
  confirmed as `ChatService.start_turn` (T1's writer already left a pointer
  comment there). Icon enum fixed to: general, player, team, match, tactics,
  transfer, injury, stats, history. Per-user stream (`user:events:{user_id}`)
  uses `XADD ... MAXLEN ~ 1000` instead of the turn stream's TTL, since it's
  long-lived across the whole session rather than scoped to one turn.
- 2026-09-24: T2 done, commit 08881d4. Spot-verified (re-ran the 6 new tests,
  read the `categorize_conversation_task`/`chat_service.py`/`worker.py`/
  `pool.py` diffs directly) — correct. Discovered pre-existing systemic bug
  confirmed independently on the same broken fixture pattern; new T2 test
  fixtures sidestep it by passing `name` as its own bound param rather than
  reproducing the bug.
- 2026-09-24: Starting T3 (POST send endpoint, added alongside WS).
- 2026-09-24: T3 done. `TurnAlreadyInProgress` moved from `live_router.py` to
  the shared `src/domain/chat/exceptions/chat_exceptions.py` (now also
  carries `TURN_ALREADY_IN_PROGRESS_DETAIL`, the message both send paths
  return) since a second router now needs it -- exactly the case AGENTS.md's
  domain-exceptions guidance describes. `_chat_service` was similarly
  promoted from a private helper in `live_router.py` to a public
  `build_chat_service` in new `src/api/v1/chat/services/chat_service_factory.py`
  (an api-layer application service reusable across controllers, per
  AGENTS.md's routers/services/dtos folder convention) rather than importing
  a leading-underscore symbol across modules. `live_router.py`'s WS route
  body (`accept_chat_message`, `_pump`, `_receive`, `conversation_live`) was
  not touched beyond these two import/call-site swaps -- behavior is
  unchanged, confirmed by its own existing test suite
  (`test_conversation_live.py`, 4/4 still green). New
  `POST /conversations/{id}/messages` added to `conversation_router.py`,
  mirroring `accept_chat_message` exactly: `start_turn` -> `SET NX EX`
  reservation -> `persist_user_message` -> `XADD UserMessageEvent` ->
  `enqueue_chat_reply`; catches `ConversationOwnershipError` -> 403
  ("Conversation not found", matching the WS path's own detail string) and
  `TurnAlreadyInProgress` -> 409. New `SendMessageRequest`/`SendMessageResponse`
  DTOs in `conversation_dtos.py` (8000-char cap -- no limit existed on the WS
  frame to match; request content is stripped and rejected if blank via a
  `field_validator`, mirroring the WS path's `message.strip()` check).
  TDD: RED confirmed first (3 new tests failing -- 405/AttributeError against
  the not-yet-existing endpoint and import), then GREEN (11/11 in
  `test_conversation_endpoints.py`). Also found and fixed (in-file only,
  minimal) the same pre-existing seed-user-fixture systemic bug flagged in
  T1/T2 in `test_conversation_endpoints.py` and `test_conversation_live.py`
  themselves -- it was blocking every test in both files, including
  pre-existing ones, not just the new ones; same established one-line fix
  (bind `name` as its own param) already used in T1/T2's own test files. Full
  `tests/` run is flaky independent of this change (connection/data-leak
  issues across the whole suite, non-deterministic failure sets between two
  runs) -- out of scope, not touched; all files this task actually changed
  or depends on pass cleanly in isolation (21/21 across
  `test_conversation_endpoints.py`, `test_conversation_live.py`,
  `test_chat_service_start_turn.py`, `test_categorize_conversation_task.py`).
  `ruff check` + `ruff format` clean on every touched file.
- 2026-09-24: T3 independently re-verified (re-ran 15 tests, read
  `live_router.py`'s diff directly — confirmed pure import-swap refactor, WS
  body genuinely unchanged).
- 2026-09-24: Starting T4 (merged SSE endpoint, remove WS). Also splitting
  `chat_tasks.py` (414 lines, over this repo's 400-line file cap) into
  `chat_streams.py` (keys/cursors/serialization helpers) + `chat_tasks.py`
  (the two Arq job functions only), since the SSE endpoint's new cursor
  helpers would have pushed it further over the cap.
- 2026-09-24: T4 done. Split verified first (moved every non-job symbol from
  `chat_tasks.py` into new `chat_streams.py` verbatim, added two new cursor
  helpers -- `resume_turn_cursor` (promoted from `live_router.py`'s private
  `_resume_cursor`) and `last_user_events_cursor` (mirrors `last_stream_cursor`
  for the per-user stream, always starting at the tail) -- then ran the full
  set of dependent test files to confirm the split alone broke nothing before
  adding any new behavior: 18/18 passed
  (`test_generate_chat_reply_task.py`, `test_categorize_conversation_task.py`,
  `test_conversation_endpoints.py`). `chat_tasks.py` 414 -> 256 lines;
  `chat_streams.py` new at 211 lines.
  New `GET /conversations/{id}/events` SSE endpoint added to
  `conversation_router.py` (360 lines after -- stayed under the cap, no
  separate router file needed). `event: turn` / `event: conversation_updated`
  framing helpers added alongside `client_message` in `sse.py`
  (`user_event_message`). `id:` line is always the combined
  `{turn_cursor}|{user_cursor}` pair. Keep-alive comment every ~15 empty
  1s-blocked polls. Disconnect checked once per loop iteration.
  TDD: RED was genuinely instructive here, not just procedural -- the first
  full test run (5 new SSE tests) hung indefinitely. Root-caused by reading
  httpx's `ASGITransport` source directly: it always fully drains the ASGI
  app (buffering the entire response body) before `handle_async_request`
  returns *anything*, including headers/status -- incompatible with this
  endpoint's deliberately-infinite generator, regardless of whether the test
  used `.get()` or `.stream()`. Fixed by switching the new
  `test_conversation_events.py` to the same real-`uvicorn.Server`-on-a-
  free-port pattern `test_conversation_live.py` used for the WS route (a
  real socket streams incrementally; `ASGITransport` does not) -- confirmed
  this by reading `test_conversation_live.py`'s `live_port` fixture before
  deleting that file. After the fix: GREEN, 5/5 new SSE tests passed
  (pre-seeded turn-stream delivery, pre-seeded user-stream delivery, resume
  from a captured `Last-Event-ID` not re-delivering already-seen entries on
  either stream half independently, 404 for missing and for another user's
  conversation).
  `live_router.py` deleted (confirmed first, per the task's own instruction,
  that nothing else imports `_ticket_key`/`mint_ws_ticket`/`TurnAlreadyInProgress`
  from it and that `ws-tickets`/`ws_tickets` have no other references --
  clean). Its import + registration removed from `main.py`.
  `test_conversation_live.py` deleted too (not explicitly named in the task,
  but it exclusively tested the now-deleted WS route and ticket endpoint --
  keeping it would leave a test permanently red against removed code).
  Docstrings/comments in five other files that referenced the now-deleted
  `live_router.py` were updated to stop pointing at it (`chat_tasks.py`'s
  module docstring, `conversation_router.py`'s `send_message` description,
  `chat_service_factory.py`, `domain/chat/tools/registry.py`,
  `domain/chat/exceptions/chat_exceptions.py`'s `TurnAlreadyInProgress`
  docstring, `conversation_dtos.py`'s `SendMessageRequest`/`_SEND_MESSAGE_MAX_LENGTH`
  comments) -- no functional change, just removing dangling references.
  Also fixed (same established one-line pattern as T1/T2/T3) the pre-existing
  seed-user-fixture systemic bug in `test_generate_chat_reply_task.py`, since
  it was blocking every test in that file and this task's import-split
  touches it.
  Full relevant regression: 24/24 passed across
  `test_conversation_events.py`, `test_conversation_endpoints.py`,
  `test_generate_chat_reply_task.py`, `test_categorize_conversation_task.py`,
  `test_chat_service_start_turn.py`. Broader sweep (`tests/ -k "chat or
  conversation"`): 38 passed, 6 errors -- all 6 in
  `tests/integration/infra/test_chat_message_repository.py`, the same
  pre-existing systemic bug, a file this task never touches (left as-is,
  consistent with T1-T3 precedent of only fixing it in files this task's own
  changes touch). Full `tests/` run: 154 passed, 5 failed, 25 errored, all in
  files this task does not touch and does not depend on (ingestion, identity
  links, tool_call_executor, task_error_handling) -- confirmed via import
  grep that none of them import anything from `chat_tasks`/`chat_streams`/
  `conversation_router`/`sse`/`live_router`; same flaky-suite-independent-of-
  this-change pattern T3 already documented.
  `ruff check` + `ruff format` clean on every touched file (one `ruff format`
  line-wrap in `conversation_router.py`, no logic change).
- 2026-09-24: T5 done, commit 4e656f2. A real race condition was caught by
  the writer's own live browser testing (not by unit tests): opening the SSE
  connection before a brand-new conversation's first POST creates the row
  404s it, and unlike WebSocket, `EventSource` never retries after a non-2xx
  initial response -- permanently stranding the connection, not just
  delaying it. Fixed by deferring `ensureEvents` until after the send
  succeeds, only for the newly-minted-conversation case. Verified
  independently: re-ran the full frontend suite myself (63/64 passed, the
  one failure in `login-form.test.tsx` confirmed pre-existing and unrelated
  by rg-scoping the diff — that file was never touched), grepped the whole
  `frontend/` tree for WebSocket/live-ticket/conversation-live references
  (zero remain outside two explanatory comments), and read every changed
  file directly: `conversation-events.ts`, the race-condition fix in
  `use-chat-thread.ts`, the SSE proxy route (independently confirmed its
  `cacheComponents: true` / route-segment-config claim against
  `next.config.ts` and the local Next 16 docs, not just trusted the writer's
  citation), `apply-live-event.ts`, and `use-conversation-list.ts`. All
  correct.

## Status: feature complete (T1-T5), then one real gap found in use
All 5 original tasks done, verified, and committed as 5 work-unit commits
plus one small fix commit (icon exposed on `ConversationSummaryDto`) on
`claude/chat-categorization-realtime-sync-b5bee9`. No WebSocket code remains
anywhere in the app.

- [x] **T6 — Dedicated per-user SSE endpoint: fix cross-window sync**
  (route: split into a backend writer then a frontend writer, same reasoning
  as T1-T4/T5 — the backend event contract needs to be final before the
  frontend consumer is written)
  - User report (2026-09-24): created a conversation in one browser window,
    it never appeared in a second window's sidebar. Root cause confirmed by
    reading the code, not assumed: (1) there was no "conversation created"
    event at all, only "categorized" — a brand-new conversation had no
    broadcast mechanism whatsoever; (2) `GET /conversations/{id}/events` is
    per-conversation-scoped and only opens once a conversation is selected
    (`ensureEvents` in `use-chat-thread.ts` is gated on `urlConversationId`),
    so a window sitting on the empty `/home` screen has no live connection
    at all, independent of (1).
  - Fix: a genuinely per-user `GET /users/events` SSE endpoint (no
    `conversation_id`, just the authenticated user's own stream), opened
    once by `useConversationList` for as long as the sidebar is mounted —
    not gated on any conversation being selected. New `ConversationCreatedEvent`
    published to the existing `user:events:{user_id}` stream from
    `ChatService.start_turn` when `created` is `True` (same stream, same
    `MAXLEN` trimming `categorize_conversation_task` already uses — direct
    precedent, `start_turn` already imports infra directly for
    `enqueue_categorize_conversation`).
  - Un-merge `GET /conversations/{id}/events` back down to turn-stream-only
    now that the dedicated endpoint supersedes its user-stream half —
    the pipe-delimited combined `Last-Event-ID`/multi-key `XREAD` complexity
    T4 introduced goes away; existing `test_conversation_events.py`
    assertions about `conversation_updated` frames move to a new test file
    for the user-events endpoint.
  - Frontend: new `user-events.ts` (types + `connectUserEvents`), new
    `/api/users/events` proxy route, `useConversationList` owns the
    connection and both prepends (`conversation_created`, deduped against
    whatever the existing `isSending`-toggle refetch already added) and
    patches in place (`conversation_updated`, unchanged logic). Remove the
    now-redundant `conversation_updated` routing from `use-chat-thread.ts`/
    `conversation-events.ts`/`home-shell.tsx` — that event no longer travels
    over the per-conversation connection.
  - Leave the existing `isSending`-toggle `refreshConversations()` in
    `home-shell.tsx` alone — it still earns its keep for `updated_at`-based
    reordering on the sending window itself, which this fix does not
    replace.

## Progress (T6)
- 2026-09-24: T6 backend done. Two deviations from spec, both verified
  legitimate before accepting them: (1) `chat_service.py` needed
  `user_events_key`/`ConversationCreatedEvent` from `chat_streams.py`, but
  `chat_streams.py` already imported `ChatTurnEvent`/`chat_turn_event_payload`
  from `chat_service.py` since T4 — a genuine circular import, confirmed by
  reading both files, not assumed. Fixed by extracting the shared event
  vocabulary into a new `chat_turn_events.py` that both import from. (2) That
  split was also forced independently: `chat_service.py` was already 406
  lines (confirmed via `git show 4e656f2:...`), over the 400-line cap,
  *before* this task added anything. Both files now under the cap (275 +
  176). New `GET /users/events` (`user_events_router.py`) matches spec
  exactly. `GET /conversations/{id}/events` un-merged back to turn-only,
  proven (not just claimed) by a test that seeds an entry on the user stream
  alongside a turn entry and asserts only the turn frame arrives. Verified
  independently: re-ran 26 tests myself, confirmed the app boots with 25
  routes (was 24), read every diff directly including the exact `start_turn`
  XADD block and the generalized `user_event_message` helper in `sse.py` —
  all correct. `ruff` clean on every touched file (one unrelated
  pre-existing formatting drift in `player_club_career_repository.py`,
  confirmed untouched by this task, left alone).
- 2026-09-24: Starting T6 frontend (dedicated user-events connection,
  sidebar prepend-on-create).
- 2026-09-24: T6 frontend done. New `user-events.ts`/`connectUserEvents` +
  `/api/users/events` proxy route, `useConversationList` owns the connection
  (opened on mount, independent of conversation selection) with a
  dedupe-by-id prepend for `conversation_created` and the existing
  `applyConversationUpdate` for `conversation_updated`. Removed the now-dead
  `onConversationUpdated` prop/branch from `use-chat-thread.ts`/
  `home-shell.tsx` and `ConversationUpdatedEvent` from
  `conversation-events.ts` (that connection is turn-only now, matching the
  backend contract change). Verified independently: re-ran 31 tests (both
  touched files) plus the full suite (66/67, same pre-existing unrelated
  `login-form.test.tsx` failure already documented for T5), read every diff
  directly (`use-conversation-list.ts`'s dedupe logic, `user-events.ts`, the
  new proxy route, and the three clean-removal diffs), and traced all 6
  `eslint` findings to exact pre-existing lines this task never touched —
  none belong to the new code. **Manually verified the actual reported bug
  is fixed**: two real browser tabs, tab B sitting on the empty `/home`
  screen with nothing selected, conversation created in tab A appeared live
  in tab B's sidebar with no reload, first as the new row and then with its
  categorized title once the job resolved. One process note: the writer's
  own `git stash` (to check a TypeScript baseline) briefly touched the
  shared stash stack; recovered via the documented safe procedure (unique
  tag, `apply <sha>` not `pop`, verified, dropped) — confirmed the stash
  list is empty and the final diff matches exactly what was intended, no
  other session's work was disturbed.

## Status: feature complete, including the cross-window fix
All of T1-T6 done, verified, and committed as 8 work-unit commits on
`claude/chat-categorization-realtime-sync-b5bee9`. The originally reported
bug (a new conversation not appearing in a second window) is fixed and
manually confirmed via a real two-tab test, not just unit tests. PR opens
when the user asks.
