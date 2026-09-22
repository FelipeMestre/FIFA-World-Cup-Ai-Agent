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
- [ ] **T4 — Wire chat endpoint**: accept client-supplied conversation UUID,
      get-or-create conversation + insert messages/widgets in one
      transaction, ownership check, then best-effort Redis write-through
      (log + swallow failure).
- [ ] **T5 — Sidebar list + title endpoints**: `GET /conversations`
      (current user's conversations, ordered by last activity),
      `PATCH /conversations/{id}` (title edit, ownership-checked).
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
