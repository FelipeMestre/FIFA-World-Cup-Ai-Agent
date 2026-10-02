"""Rebuilds the LLM prompt history from Postgres when the Redis cache is empty.

KV/prefix-cache safety rules (the reason this is deliberately minimal):
- Output is only `Message(role, content)` text pairs, in `sequence` order --
  exactly what the LLM saw (user text) and produced (assistant text). No
  widgets, metadata, reasoning, tool messages, markers or placeholders.
- Deterministic and append-only: the same rows always rebuild to the same
  messages, and windowing only ever drops WHOLE oldest turns, so the
  surviving prefix does not shift while the history stays under budget.
- Orphan user rows (failed turns, and the just-persisted current user message
  `send_message` appends itself) are not part of the history.
"""

from typing import Protocol
from uuid import UUID

from src.domain.chat.model.message import Message
from src.infra.tokens.interfaces.token_counter_interface import TokenCounterInterface

Turn = tuple[Message, Message]


class PromptTurnSource(Protocol):
    async def list_prompt_turns(self, conversation_id: UUID) -> list[Message]: ...


class ChatHistoryRebuildService:
    def __init__(
        self,
        prompt_turn_source: PromptTurnSource,
        token_counter: TokenCounterInterface,
        token_budget: int,
    ) -> None:
        if token_budget <= 0:
            raise ValueError(f"token_budget must be positive, got {token_budget}")
        self._prompt_turn_source = prompt_turn_source
        self._token_counter = token_counter
        self._token_budget = token_budget

    async def rebuild(self, conversation_id: UUID) -> list[Message]:
        rows = await self._prompt_turn_source.list_prompt_turns(conversation_id)
        turns = _pair_complete_turns(rows)
        kept_turns = self._window_to_budget(turns)
        return [
            Message(role=message.role, content=message.content)
            for turn in kept_turns
            for message in turn
        ]

    def _window_to_budget(self, turns: list[Turn]) -> list[Turn]:
        """Keeps the newest turns that fit; stops at the first (newest-first)
        turn that does not, so an older small turn is never kept across a
        dropped larger one."""
        kept: list[Turn] = []
        used_tokens = 0
        for turn in reversed(turns):
            turn_tokens = sum(self._token_counter.count_tokens(m.content) for m in turn)
            if used_tokens + turn_tokens > self._token_budget:
                break
            used_tokens += turn_tokens
            kept.append(turn)
        kept.reverse()
        return kept


def _pair_complete_turns(rows: list[Message]) -> list[Turn]:
    """A turn is a user row immediately followed by an assistant row. Any
    other row (user without a reply, stray assistant) is dropped."""
    turns: list[Turn] = []
    for user_row, reply_row in zip(rows, rows[1:], strict=False):
        if user_row.role == "user" and reply_row.role == "assistant":
            turns.append((user_row, reply_row))
    return turns
