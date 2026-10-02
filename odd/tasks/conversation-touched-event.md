# conversation-touched-event

## Objective
Sending a message to an old conversation must move it to the top of the sidebar ("Today" group) in EVERY open tab, live.

## Problem
`conversation_repo.touch()` bumps `updated_at` but no user-stream event announces it. `/users/events` only carries `conversation_created` and `conversation_updated` (categorization). Frontend `applyConversationUpdate` patches in place and never reorders. Other tabs never learn of the bump.

## Design
- New user-stream event `ConversationTouchedEvent` (`conversation_id`, `updated_at`), serialized to `user:events:{uid}`, mapped to wire type `conversation_touched` in `api/v1/chat/sse.py` (`_USER_EVENT_WIRE_TYPE`) and documented in `user_events_router.py`.
- Published (XADD, fail-soft: log, never fail the turn) right after `touch()` in BOTH places: `persist_user_message` path (row jumps when the user hits send) and end-of-turn persistence (refresh).
- Frontend: `connectUserEvents` / `UserEvent` types handle `conversation_touched`; `use-conversation-list` moves the row to the top with the new `updatedAt` (no-op if the row is not in the list yet; idempotent for the sending tab).

## Tasks
- [x] T1 backend: event class + serializer + SSE wire mapping (+ unit tests)
- [x] T2 backend: touch in persist_user_message + publish at both touch points, fail-soft (+ unit tests)
- [~] T3 frontend: user-events types/parsing + list hook reorder (+ tests per frontend test conventions)

## Constraints
Strict TDD where a runner exists; ruff; files < 400 lines; English artifacts; conventional commits, no AI attribution; same branch `feat/chat-history-rebuild` (PR #37); work only in this worktree; no docker cp/exec; commit locally, no push.

## Progress / evidence
- T1 (7301621): RED observed (ImportError ConversationTouchedEvent), GREEN 3 tests in tests/unit/infra/test_conversation_touched_event.py.
- T2 (2346b5b): RED observed (collection failure, then signature/behavior), GREEN: `touch` now returns real `updated_at` (RETURNING); `persist_user_message(conversation_id, user_id, ...)` touches in the same txn, publishes after commit; end-of-turn publishes after commit; `publish_conversation_touched` fail-soft in chat_streams.py. `pytest tests/unit`: 148 passed; ruff format clean, ruff check only the 5 known E501 in SYSTEM_PROMPT. Integration tests NOT run (need Postgres/Redis).
- T3 (frontend commit, see git log): user-events.ts union + listener, pure `touchConversation` (touch-conversation.ts), hook handler, tests added (touch-conversation.test.ts, use-conversation-list.test.tsx). NOT RUN: frontend has no node_modules in this worktree, so vitest/tsc/eslint could not execute. Box left as [~] until run.
- Routes: all inline by single writer (delegated).
