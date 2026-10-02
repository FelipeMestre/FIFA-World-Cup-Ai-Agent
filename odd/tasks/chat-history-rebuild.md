# chat-history-rebuild

## Objective
When the Redis prompt-history cache is empty (miss, 24h expiry, flush, failed turn), rebuild the LLM prompt history from Postgres so the model keeps prior context, while preserving the provider KV/prefix cache.

## Problem
`ChatService.send_message` reads history only from Redis (`chat:conversation:{id}`). On a miss the LLM gets no earlier context. Docstrings call the cache "rebuildable", but nothing rebuilds it.

## Design rules (KV-cache safety)
- Rebuilt history contains ONLY what the LLM actually saw/produced: completed user text + assistant text, in `sequence` order, as `{"role","content"}`.
- Never included: widgets, metadata, reasoning, tool messages, system prompt/match directive, placeholders, markers, "[widget shown]" text, timestamps.
- Orphan user messages (failed turns: user row with no following assistant row, incl. the just-persisted current user message) are not part of the rebuilt history; `send_message` appends the current user message itself, exactly as today.
- Assistant `content` in Postgres == `reply_content` written to the cache, so rebuilt == cached bytes.
- Deterministic and append-only: same rows -> same output. Windowing drops WHOLE oldest turns (user+assistant pair) against a token budget; drop is stable (does not shift every turn unless budget is exceeded).
- After rebuild, write result to the Redis cache (same TTL) so later turns reuse the stable prefix.

## Token counting
- `tiktoken` (`o200k_base`), behind `TokenCounterInterface` (infra/tokens: config, interfaces, repositories-style private impl + provider).
- Fail-soft: if encoding cannot load (offline), fall back to `ceil(len(text)/4)` and log a warning.
- Budget configurable via settings (`CHAT_HISTORY_TOKEN_BUDGET`, sensible default e.g. 50000), per-domain BaseSettings.

## Tasks
- [x] T1 token counter interface + tiktoken impl + fallback (+ tests)
- [x] T2 repository method on ChatMessageRepositoryInterface: prompt-oriented list (no widgets, no ownership join needed beyond conversation id; text turns only) (+ integration test vs real Postgres)
- [x] T3 domain service `chat_history_rebuild_service.py`: pairs turns, drops orphans, windows by budget (+ unit tests)
- [x] T4 wire into `ChatService.send_message`: if cache history empty -> rebuild + save to cache (+ test)
- [x] T5 add `tiktoken` to backend/requirements.txt; docs note in README/AGENTS if relevant

## Constraints
- Strict TDD (RED->GREEN->REFACTOR), pytest asyncio_mode=auto, ruff. No mocks of DB; real fixtures.
- Files < 400 lines. English artifacts. Conventional commits, no AI attribution lines.
- Work only in this worktree. Do NOT docker cp/exec into containers (bind-mounted to another worktree). Use the main checkout venv interpreter.
- No push, no PR.

## Progress / evidence
- T1 433035c: token counter + fallback. 4 unit tests pass (RED observed first: ModuleNotFoundError).
- T2 68ba760: `list_prompt_turns` (role+content, sequence order, no widget load). Integration tests written in tests/integration/infra/test_chat_message_repository.py but NOT RUN: no Postgres/Redis/docker available in this environment (RED/GREEN not observed for these two tests; only module import + ruff verified).
- T3 26ed677: ChatHistoryRebuildService + ChatHistoryConfig (CHAT_HISTORY_TOKEN_BUDGET, default 50000). 14 unit tests pass (RED first: collection ImportError). Covers orphans, stray assistant, ordering, whole-turn windowing, fallback counter path, no widgets/metadata/tool fields.
- T4 25a1dc8: ChatService._load_prompt_history (cache -> rebuild -> save with CONVERSATION_HISTORY_TTL_SECONDS; fail-soft). 5 unit tests pass (RED first: unexpected kwarg).
- T5: tiktoken==0.14.0 (+ regex, requests, urllib3 pins) in requirements.txt (433035c); env.example.txt note (last commit).
- Verification: `pytest tests/unit` -> 141 passed (run with dummy DATABASE_URL/REDIS_URL/OPENROUTER_API_KEY; unit tests make no connections). `ruff format --check` clean; `ruff check src tests` -> 5 E501 errors, all pre-existing in chat_service.py SYSTEM_PROMPT (same count on base).
- Not verified: real-Postgres integration tests (T2) and the existing integration suite.
