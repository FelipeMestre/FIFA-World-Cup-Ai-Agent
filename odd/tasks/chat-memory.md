# Chat memory persistence

Branch: `feature/chat-memory`

## Objective

Move chat conversation history from Redis-only (TTL-bound, lossy) to a durable
Postgres append-only log as source of truth, with Redis as a read-through
cache. Add conversation identity (client-generated UUID in the URL), an
editable conversation title for the sidebar, and a sidebar conversation list.

## Problem / why

Today `Conversation`/`Message` are plain dataclasses persisted only in Redis
(`chat:conversation:` key prefix, TTL-bound). If Redis falls over, or a
message is written to Redis but the app restarts before any durable copy
exists, the conversation is gone. There is no way to list a user's past
conversations, no conversation title, and no per-user ownership check.

## Decisions already made (do not re-litigate)

- Postgres is the durable source of truth; `chat_message` is append-only,
  never UPDATEd. Redis is a read-through cache, written to directly/
  synchronously in the endpoint after the Postgres transaction commits
  (no CDC/outbox — explicitly deferred as unjustified for this demo-stage
  system). A Redis write failure must not fail the request.
- Widgets attached to an assistant message live in a separate
  `chat_message_widget` table (FK to `chat_message.id`), never merged into
  `chat_message.content`, to protect LLM prompt-cache stability.
- Conversation id is a client-generated UUID (`crypto.randomUUID()`),
  pushed into the URL before the first message is sent. Backend does a
  get-or-create of the `conversation` row keyed by that UUID in the same
  transaction as the first `chat_message` insert.
- `conversation.user_id` is a real FK to the local `user.id` (int) — auth in
  this codebase is self-issued JWT with a local `user` table, NOT Auth0
  (verified by exploration; AGENTS.md's Auth0 example does not reflect this
  project's actual auth).
- Every read/write on a conversation must check
  `conversation.user_id == current_user.id` server-side. UUID unguessability
  is never treated as authorization.
- `conversation.title` is a plain mutable string column, editable via PATCH.
  Initial value = truncated first user message (~40 chars) for now;
  LLM-generated titling is an explicitly deferred future improvement (must
  not be designed against — keep `title` a plain column).

## Codebase facts from exploration (2026-09-22)

- No `conversation`/`message` table exists in Postgres today. Domain
  `Conversation`/`Message` in `backend/src/domain/chat/model/` are plain
  dataclasses; conversation id is currently generated server-side in
  `chat_service.py:111` (`str(uuid.uuid4())`) — this must move to
  client-generated and passed in.
- Redis already has `ConversationCacheRepositoryInterface` /
  `_RedisConversationCacheRepository` (`backend/src/infra/redis/repositories/
  conversation_cache_repository.py`) under key prefix `chat:conversation:`.
  Its `save_history`/`get_history` only round-trip `role`+`content` today —
  will need to stay in sync with whatever the DB-backed history shape is.
- All Postgres schemas use SQLAlchemy 2.0 `Mapped`/`mapped_column`, share
  `Base`/`metadata` from `backend/src/infra/postgres/schemas/base.py`
  (fixed index/constraint naming convention). `_at` columns are always
  `DateTime(timezone=True)`. No UUID PK precedent exists yet — this feature
  introduces the first one.
- Repository shape: `Protocol` interface in `interfaces/`, private
  `_SqlAlchemy<Entity>Repository`/`_Redis<Entity>Repository` class + a
  `_to_domain` mapper, public `get_<entity>_repository(...)` FastAPI
  dependency factory. Follow this exactly for new repositories.
- Migrations: `backend/migrations/versions/`, filename
  `YYYY-MM-DD_slug.py` (from `alembic.ini` `file_template`). Existing
  migrations favor raw `op.execute(...)` for alters; `op.create_table` is
  the right call here since we're creating new tables (see
  `2026-09-19_add_real_match_tables_and_ingestion_job.py` for a
  `create_table`-with-FK example to match style against, not yet read in
  full).
- Chat router currently only gates on `JwtDataDep`, does not yet extract/use
  `user.id` in the chat flow — that wiring is new for this feature.

## Task Progress

TDD mode: to resolve when apply starts (check `sdd-init/{project}` /
project test config; this repo uses `pytest` + `httpx.AsyncClient` +
`ASGITransport` per AGENTS.md).

Route legend: [inline] = direct edit, [delegated] = bounded sub-agent writer.

- [x] **T1 — Postgres schema files** (delegated: 3 new files, non-trivial)
      `conversation_schema.py`, `chat_message_schema.py`,
      `chat_message_widget_schema.py` under
      `backend/src/infra/postgres/schemas/`, matching existing conventions
      (Mapped/mapped_column, shared Base, DateTime(timezone=True), FK to
      `user.id`). First UUID PK in the codebase — use
      `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)`.
      Done 2026-09-22: files created, registered in `schemas/__init__.py`,
      `ruff check`/`ruff format` clean.
- [x] **T2 — Alembic migration** (delegated, same writer as T1)
      `op.create_table` for `conversation`, `chat_message`,
      `chat_message_widget` with FKs, indexes on `conversation.user_id` and
      `chat_message.conversation_id`, unique constraint on
      `(conversation_id, sequence)` for `chat_message`. Filename
      `<today>_add_chat_persistence_tables.py`.
      Done 2026-09-22: `backend/migrations/versions/
      2026-09-22_add_chat_persistence_tables.py`, revision `9c2f6a1d84b7`,
      down_revision `5d0e3a7c19f4`. Verified against local docker Postgres
      (`world-cup-ai-scout-postgres`): `alembic upgrade head` →
      `downgrade -1` → `upgrade head` all succeeded; generated constraint/
      index names confirmed to match `POSTGRES_INDEXES_NAMING_CONVENTION`.
- [x] **T3 — Repository interfaces + implementations**
      `ConversationRepositoryInterface`/`_SqlAlchemyConversationRepository`
      (`get_or_create`, `get_owned`, `list_for_user`, `update_title`,
      `touch`) and `ChatMessageRepositoryInterface`/
      `_SqlAlchemyChatMessageRepository` (`append_message`,
      `list_for_conversation`), following the existing 3-file repo pattern.
      Done 2026-09-22: all write methods flush-only (no commit), documented
      per-method as a deliberate deviation for T4's single-transaction
      design. Added `ChatMessage`/`ChatMessageWidget` domain dataclasses and
      `ConversationOwnershipError` (`domain/chat/exceptions/chat_exceptions.py`).
      Updated the previously-dead `Conversation` dataclass in place
      (`id: UUID`, `user_id`, `title`, `updated_at`) after confirming via
      `rg -n "Conversation\("` that nothing constructs it yet (`chat_service.py`
      only passes a plain `conversation_id: str`, never the dataclass).
      Added a `ChatMessageSchema.widgets` relationship (`lazy="raise"`, no
      prior `relationship()` precedent in this codebase) for
      `selectinload` in `list_for_conversation`. 16 new integration tests
      in `backend/tests/integration/infra/test_conversation_repository.py`
      and `test_chat_message_repository.py`, run against local docker
      Postgres — all passing; `ruff check`/`ruff format` clean. 7
      pre-existing failures/3 errors elsewhere in the suite
      (`tool_call_executor`, `ingestion_repository`,
      `identity_link_router`, `test_chat_send_message`) are unrelated to
      this task's files and were not introduced by it.
- [x] **T4 — Wire chat endpoint**: accept client-supplied conversation UUID,
      get-or-create conversation + insert messages/widgets in one
      transaction, ownership check, then best-effort Redis write-through
      (log + swallow failure).
      Done 2026-09-22: `SendMessageRequest.conversation_id` is now a required
      `UUID` (422 on an invalid string; server-side `uuid.uuid4()` generation
      removed). `ChatService` gained `conversation_repo`/`chat_message_repo`/
      `session` constructor deps and a new `start_turn(conversation_id,
      user_id, first_message)` method the router awaits *before* opening the
      `StreamingResponse` -- so `ConversationOwnershipError` can still become
      a clean 403 (once SSE streaming starts, headers are already committed
      to 200). `send_message` now takes `user_id`, persists both messages +
      widgets + `touch()` + one `session.commit()` right before
      `message_done`, wrapped in try/except: a Postgres failure yields a new
      `PersistenceFailedEvent` domain event (mapped to the existing `error`
      SSE vocabulary via `ErrorEventDto` in the router -- no new DTO needed)
      then still finishes the turn; a Redis failure is logged and swallowed
      per the already-agreed cache design. Router extracts `user_id =
      int(jwt_data["sub"])`. Files touched: `chat_dtos.py`, `chat_router.py`,
      `chat_service.py`, `tests/integration/test_chat_send_message.py`.
      Test suite (local venv against the docker-compose Postgres/Redis on
      `localhost:55432`/`56379`, since the running `world-cup-ai-scout-backend`
      container mounts the main checkout, not this worktree): 144 passed, 7
      failed, 3 errored -- exactly the pre-existing baseline from T3's entry
      (`tool_call_executor` x3, `ingestion_repository` x2,
      `identity_link_router` x3 errors, and the one known
      `test_team_analysis_tool_streams_widget_ready_then_message_done`
      widget-ordering failure). All 3 new tests added for T4's acceptance
      criteria (two-message sequencing, cross-user 403, Postgres-row
      assertion) pass; all pre-existing `test_chat_send_message.py` tests
      updated to send a required `conversation_id` and pass.
      Gap noticed, not in scope here: there is still no "load/replay a
      conversation's messages" endpoint (T5/T6 territory) -- a page reload
      cannot yet repopulate history from Postgres.
- [x] **T5 — Sidebar list, title, and reload endpoints**: `GET /conversations`
      (current user's conversations, ordered by last activity),
      `PATCH /conversations/{id}` (title edit, ownership-checked),
      `GET /conversations/{id}/messages` (full replay — always reads
      Postgres directly, never Redis: Redis only caches flat role+content
      for the LLM prompt, it has no widget data, so a reload endpoint
      checking cache-first would silently drop widgets on a hit — decided
      2026-09-22). All three ownership-checked via `get_owned`/`update_title`
      returning `None` on missing-or-not-owned → 404 (never a 403 that would
      leak existence, consistent with T3's `get_owned` rationale).
      Done 2026-09-22: new `conversation_router.py` (`APIRouter(prefix=
      "/conversations", tags=["conversations"])`), registered in
      `main.py`'s `API_V1_ROUTERS`. New `conversation_dtos.py`
      (`ConversationSummaryDto`, `UpdateConversationTitleRequest`,
      `ConversationMessageDto`, `ConversationMessagesResponse`). `PATCH`
      injects `AsyncSession` via `get_db` and calls `session.commit()`
      itself after `update_title` succeeds, per T3's flush-only convention.
      `GET .../messages` calls `get_owned` before `list_for_conversation`
      so a non-owner 404s without a data query, even though
      `list_for_conversation` is already ownership-filtered as
      defense-in-depth. Promoted the widget_type -> `MessagePart` mapping
      (previously `chat_router.py`'s module-private `_WIDGET_TYPE_TO_PART_CLASS`)
      to `chat_dtos.py` as `WIDGET_TYPE_TO_PART_CLASS` -- both routers now
      import the one dict instead of each keeping its own copy;
      `chat_router.py` updated accordingly (import-only change, no
      behavior change). 6 new integration tests in
      `backend/tests/integration/test_conversation_endpoints.py` (list
      ordering + per-user scoping, rename + both 404 cases returning an
      identical body, replay with a widget, replay 404 for another user's
      conversation), all passing against local docker Postgres. `ruff
      check`/`ruff format` clean on every touched file.
      Full suite: 144 passed, 13 failed, 3 errored. This is 6 MORE
      failures than the previously documented baseline (7 failed/3
      errored), all 6 inside `test_chat_send_message.py` (previously
      passing tests now fail with a Postgres FK violation / `error` SSE
      event / 403 becoming 200). Verified with `git stash` that this
      reproduces identically on the pre-T5 (T4) code with none of this
      task's files present -- so it is a pre-existing bug in T4's
      `chat_service.py`/`get_db`, not something T5 introduced. Root cause:
      `get_db`'s `async with SessionFactory()` context exits (rolling back
      anything only flushed, never committed) as soon as the
      `send_message` endpoint function returns the `StreamingResponse`
      object -- before `_stream_chat_events`'s generator actually runs and
      calls `session.commit()`. So `start_turn`'s flush-only
      `get_or_create()` conversation row is rolled back before
      `send_message`'s later `chat_message` insert, which then violates
      the `chat_message_conversation_id_fkey` FK.

      **Fixed same day (commit `2775962`, orchestrator-verified, not
      delegated):** confirmed independently in an isolated worktree at the
      T4 commit (before T5 existed) that this predates T5 entirely -- a
      real T4 regression, not a test artifact of T5's new fixture. Fix:
      `start_turn` now commits immediately after `get_or_create` (its own
      atomic unit, safe before the endpoint returns). `send_message`'s
      persistence block no longer uses the request-scoped
      `self._chat_message_repo`/`self._conversation_repo`/`self._session`
      at all -- it opens its own `SessionFactory()`-backed session,
      independent of the request's dependency lifecycle, for the
      message/widget inserts + `touch()` + commit. Full suite back to the
      documented baseline exactly: 150 passed, 7 failed, 3 errored (the
      150 includes T5's 6 new tests, all green). Every other baseline
      category (`tool_call_executor` x3, `ingestion_repository` x2,
      `player_identity_link_repository` x1, `identity_link_router` x3
      errors, one widget-ordering test) is unchanged and pre-existing.
- [ ] **T6 — Frontend**: client-generated UUID on new chat, URL update,
      sidebar conversation list feature, title rename UI.

Currently in progress: **T1 + T2** (schema + migration only, per explicit
user request to start there).

## Acceptance criteria (for T1/T2 specifically)

- Schema files import `Base`/`metadata` from the existing `base.py`, no new
  metadata instance.
- `chat_message` has no `UPDATE` path anywhere in the repository layer to be
  written later (T3) — append-only is enforced at the repository level, not
  just by convention.
- Migration applies and reverts cleanly (`alembic upgrade head` /
  `alembic downgrade -1`) against the local dev DB.
- Foreign keys and indexes use the project's naming convention (verify
  generated constraint names against `POSTGRES_INDEXES_NAMING_CONVENTION`
  in `base.py`).

## Next step

Delegate T1 (schema files) to a writer sub-agent with the exact conventions
above, then T2 (migration) once schema files are settled — same writer,
same task, to keep FK/column definitions consistent between the ORM model
and the migration without a second round of context-loading.
