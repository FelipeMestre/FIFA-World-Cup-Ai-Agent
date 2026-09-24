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
  touches migration, domain model, schema, repository, interface: 5 files)
  - Alembic migration: add `icon: str` (nullable, enum-constrained at app
    level) and `title_is_generated: bool default true` to `conversation`.
  - `Conversation` dataclass: add both fields.
  - `ConversationSchema`: add both columns.
  - `ConversationRepositoryInterface` + impl: `update_category(conversation_id,
    title, icon)` (respects `title_is_generated` guard); `update_title` sets
    `title_is_generated=False`; `get_or_create` returns `(conversation,
    created: bool)`.
  - Tests: repository test for the guard behavior, `get_or_create` created-flag.

- [ ] **T2 — Categorization Arq job** (route: delegated writer — job file +
  worker registration + new stream helpers: 3 files)
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

- [ ] **T3 — POST send endpoint, replacing WS send** (route: delegated writer
  — router + service wiring: 2-3 files)
  - `POST /conversations/{id}/messages`: ownership check, `chat_service
    .start_turn` (get_or_create + created flag), reserve turn (`SET NX EX`),
    persist user message, `XADD` `UserMessageEvent`, `enqueue_chat_reply`,
    and — on `created=True` — enqueue `categorize_conversation_task`. Returns
    202 ack.
  - Tests: 202 ack shape, turn-in-progress 409 conflict preserved, categorize
    job enqueued only on first message of a new conversation.

- [ ] **T4 — Merged SSE endpoint, remove WS** (route: delegated writer —
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

- [ ] **T5 — Frontend: SSE proxy route + consumer hook** (route: delegated
  writer — proxy route + hook rewrite + list-store wiring: 3-4 files)
  - `app/api/conversations/[conversationId]/events/route.ts`: cookie-authed
    streaming proxy to backend SSE endpoint.
  - Replace `conversation-live.ts`'s WS client with an `EventSource`-based
    hook (delete hand-rolled reconnect/pending-queue logic — native resume
    replaces it).
  - Sidebar/`use-conversation-list.ts` applies `conversation_updated` events
    live regardless of which conversation is open.

- [ ] **T6 — Frontend: POST send + cleanup** (route: delegated writer —
  send function + `use-chat-thread.ts` wiring: 2-3 files)
  - New `sendMessage` as a plain `POST`, replacing the WS `send` frame.
  - Remove now-dead `live-ticket` route and any WS-specific client code.

## Acceptance criteria
- Sending a message works end-to-end via POST + SSE turn events (parity with
  today's WS behavior, including `is_generating` sidebar spinner).
- A newly created conversation gets an LLM-generated title + icon, visible on
  every open device/tab for that account without a manual reload.
- Manually renaming a conversation before categorization resolves is never
  overwritten by the categorization result.
- No WebSocket code paths remain for this feature.

## Progress
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
