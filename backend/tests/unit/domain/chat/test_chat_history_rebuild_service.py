from uuid import uuid4

import pytest

from src.domain.chat.model.message import Message
from src.domain.chat.services.chat_history_rebuild_service import ChatHistoryRebuildService
from src.infra.tokens.repositories.tiktoken_token_counter import _TiktokenTokenCounter


class _InMemoryPromptTurnSource:
    """Real in-memory implementation of the one repository method the
    service uses (not a Mock): returns the rows exactly as stored."""

    def __init__(self, turns: list[Message]) -> None:
        self._turns = turns

    async def list_prompt_turns(self, conversation_id) -> list[Message]:
        return list(self._turns)


class _WordCounter:
    """Deterministic counter: one token per whitespace-separated word."""

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _user(content: str) -> Message:
    return Message(role="user", content=content)


def _assistant(content: str) -> Message:
    return Message(role="assistant", content=content)


def _service(turns: list[Message], budget: int = 1_000) -> ChatHistoryRebuildService:
    return ChatHistoryRebuildService(
        _InMemoryPromptTurnSource(turns), _WordCounter(), token_budget=budget
    )


async def _rebuild(turns: list[Message], budget: int = 1_000) -> list[tuple[str, str]]:
    rebuilt = await _service(turns, budget).rebuild(uuid4())
    return [(m.role, m.content) for m in rebuilt]


async def test_rebuilds_complete_turns_in_order() -> None:
    result = await _rebuild(
        [_user("q1"), _assistant("a1"), _user("q2"), _assistant("a2"), _user("current")]
    )

    assert result == [("user", "q1"), ("assistant", "a1"), ("user", "q2"), ("assistant", "a2")]


async def test_empty_conversation_rebuilds_to_empty_history() -> None:
    assert await _rebuild([]) == []


async def test_only_the_current_user_message_rebuilds_to_empty_history() -> None:
    assert await _rebuild([_user("first question")]) == []


async def test_drops_trailing_current_user_message() -> None:
    result = await _rebuild([_user("q1"), _assistant("a1"), _user("current")])

    assert result == [("user", "q1"), ("assistant", "a1")]


async def test_drops_orphan_user_rows_from_failed_turns() -> None:
    result = await _rebuild(
        [
            _user("failed turn, no reply"),
            _user("retry"),
            _assistant("answer to retry"),
            _user("current"),
        ]
    )

    assert result == [("user", "retry"), ("assistant", "answer to retry")]


async def test_drops_assistant_rows_without_a_preceding_user_row() -> None:
    result = await _rebuild([_assistant("stray"), _user("q1"), _assistant("a1")])

    assert result == [("user", "q1"), ("assistant", "a1")]


async def test_rebuilt_messages_are_plain_role_content_text_only() -> None:
    rebuilt = await _service([_user("q1"), _assistant("a1")]).rebuild(uuid4())

    assert all(m.role in ("user", "assistant") for m in rebuilt)
    assert all(m.tool_call_id is None and m.name is None for m in rebuilt)
    assert [m.content for m in rebuilt] == ["q1", "a1"]


async def test_windowing_drops_whole_oldest_turns_when_over_budget() -> None:
    turns = [
        _user("one two"),  # turn 1: 4 tokens
        _assistant("three four"),
        _user("five six"),  # turn 2: 4 tokens
        _assistant("seven eight"),
        _user("nine ten"),  # turn 3: 4 tokens
        _assistant("eleven twelve"),
    ]

    result = await _rebuild(turns, budget=8)

    assert result == [
        ("user", "five six"),
        ("assistant", "seven eight"),
        ("user", "nine ten"),
        ("assistant", "eleven twelve"),
    ]


async def test_windowing_never_splits_a_turn() -> None:
    turns = [_user("a b c"), _assistant("d e f"), _user("g"), _assistant("h")]

    # Turn 1 costs 6 tokens, turn 2 costs 2: both fit at 8, only turn 2 below that.
    assert await _rebuild(turns, budget=8) == [
        ("user", "a b c"),
        ("assistant", "d e f"),
        ("user", "g"),
        ("assistant", "h"),
    ]
    assert await _rebuild(turns, budget=7) == [("user", "g"), ("assistant", "h")]


async def test_windowing_is_stable_and_does_not_shift_while_under_budget() -> None:
    turns = [_user("q1"), _assistant("a1"), _user("q2"), _assistant("a2")]

    first = await _rebuild(turns, budget=100)
    second = await _rebuild(turns, budget=100)

    assert (
        first
        == second
        == [("user", "q1"), ("assistant", "a1"), ("user", "q2"), ("assistant", "a2")]
    )


async def test_windowing_drops_all_older_turns_once_one_does_not_fit() -> None:
    turns = [
        _user("small"),
        _assistant("small"),
        _user("huge " * 50),
        _assistant("huge " * 50),
        _user("tiny"),
        _assistant("tiny"),
    ]

    result = await _rebuild(turns, budget=10)

    # The old small turn must not be resurrected past the turn that didn't fit.
    assert result == [("user", "tiny"), ("assistant", "tiny")]


async def test_a_single_turn_larger_than_the_budget_yields_empty_history() -> None:
    assert await _rebuild([_user("a b c d"), _assistant("e f g h")], budget=3) == []


async def test_window_counts_with_the_real_fallback_counter_path() -> None:
    def _offline():
        raise OSError("offline")

    service = ChatHistoryRebuildService(
        _InMemoryPromptTurnSource(
            [_user("a" * 40), _assistant("b" * 40), _user("c" * 8), _assistant("d" * 8)]
        ),
        _TiktokenTokenCounter(encoding_loader=_offline),
        token_budget=10,  # fallback: 10 + 10 tokens for turn 1, 2 + 2 for turn 2
    )

    rebuilt = await service.rebuild(uuid4())

    assert [(m.role, m.content) for m in rebuilt] == [("user", "c" * 8), ("assistant", "d" * 8)]


def test_rejects_a_non_positive_token_budget() -> None:
    with pytest.raises(ValueError, match="token_budget"):
        _service([], budget=0)
