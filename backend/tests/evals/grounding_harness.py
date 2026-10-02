"""Harness for counterfactual grounding evals.

A counterfactual eval swaps the data behind a tool for values that differ from
reality and asserts the real LLM's answer follows the tool, not its training
memory. Only repositories are faked (see `fakes.py`): the real tool handlers,
registry, `ToolCallExecutor`, system prompt and tool schemas run exactly as in
production, so the JSON the model reads has production's exact shape.

These evals call the real model through OpenRouter. They are opt-in
(`pytest -m llm_eval`) and need `OPENROUTER_API_KEY`.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from src.domain.chat.services.chat_service import DEFAULT_TOOL_SCHEMAS, SYSTEM_PROMPT
from src.domain.chat.services.tool_call_executor import (
    ToolCallExecutor,
    ToolCallRequestedEvent,
    TurnResolvedEvent,
)
from src.domain.chat.tools.registry import ToolDefinition, build_tool_registry
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.schemas import ChatCompletionResult
from tests.evals.fakes import (
    UnusedMatchRepository,
    UnusedPlayerRepository,
    UnusedTeamRepository,
)

EVAL_ATTEMPTS = int(os.environ.get("EVAL_ATTEMPTS", "3"))
EVAL_MIN_PASSES = int(os.environ.get("EVAL_MIN_PASSES", "2"))


@dataclass(frozen=True)
class ToolInvocation:
    """One validated tool call: the tool name and its parsed arguments (defaults included)."""

    name: str
    arguments: dict


@dataclass(frozen=True)
class ObservedTurn:
    answer: str
    tools_called: list[str]
    repository_calls: list[str] = field(default_factory=list)
    tool_invocations: list[ToolInvocation] = field(default_factory=list)


@dataclass(frozen=True)
class TurnSetup:
    """Everything a turn needs besides the question. Unset repositories raise
    `NotImplementedError` if a tool touches them. `registry_overrides`
    replaces whole tool definitions (used to fake the static clock tool).
    `extra_system_messages` follow the system prompt, like the match-chip directive.
    """

    team_repo: object = field(default_factory=UnusedTeamRepository)
    player_repo: object = field(default_factory=UnusedPlayerRepository)
    match_repo: object = field(default_factory=UnusedMatchRepository)
    registry_overrides: dict[str, ToolDefinition] = field(default_factory=dict)
    extra_system_messages: tuple[str, ...] = ()


async def run_turn(question: str, setup: TurnSetup) -> ObservedTurn:
    """Drive one real-LLM chat turn against the fake repositories in `setup`."""
    registry = {
        **build_tool_registry(setup.team_repo, setup.player_repo, setup.match_repo),
        **setup.registry_overrides,
    }
    invocations: list[ToolInvocation] = []
    registry = {name: _recording(name, tool, invocations) for name, tool in registry.items()}
    calls_before = _repository_call_counts(setup)
    executor = ToolCallExecutor(get_openrouter_client(), registry)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *({"role": "system", "content": text} for text in setup.extra_system_messages),
        {"role": "user", "content": question},
    ]

    tools_called: list[str] = []
    final_answer: str | None = None
    async for event in executor.run(messages, DEFAULT_TOOL_SCHEMAS):
        if isinstance(event, ToolCallRequestedEvent):
            tools_called.append(event.name)
        elif isinstance(event, TurnResolvedEvent):
            assert isinstance(event.result, ChatCompletionResult), "tool loop hit its iteration cap"
            final_answer = event.result.content

    assert final_answer is not None, "the turn ended without a TurnResolvedEvent"
    return ObservedTurn(
        answer=final_answer,
        tools_called=tools_called,
        repository_calls=_new_repository_calls(setup, calls_before),
        tool_invocations=invocations,
    )


async def passes_enough_attempts(
    question: str, setup: TurnSetup, check: Callable[[ObservedTurn], None]
) -> None:
    """Run the turn `EVAL_ATTEMPTS` times; require `EVAL_MIN_PASSES` clean
    passes, since a real model is non-deterministic. `check(turn)` raises
    `AssertionError` on a violation.
    """
    failures: list[str] = []
    for _ in range(EVAL_ATTEMPTS):
        turn = await run_turn(question, setup)
        try:
            check(turn)
        except AssertionError as error:
            failures.append(f"{error}\n  answer: {turn.answer!r}")
    passes = EVAL_ATTEMPTS - len(failures)
    assert passes >= EVAL_MIN_PASSES, (
        f"only {passes}/{EVAL_ATTEMPTS} attempts passed (need {EVAL_MIN_PASSES}):\n"
        + "\n".join(failures)
    )


def _recording(name: str, tool: ToolDefinition, invocations: list[ToolInvocation]):
    """Same tool, but every validated call is appended to `invocations`."""

    async def handler(args: BaseModel):
        invocations.append(ToolInvocation(name=name, arguments=args.model_dump()))
        return await tool.handler(args)

    return tool.model_copy(update={"handler": handler})


def _repositories(setup: TurnSetup) -> list[object]:
    """Repositories that log their calls; real repositories do not and are skipped."""
    candidates = [setup.team_repo, setup.player_repo, setup.match_repo]
    return [repository for repository in candidates if hasattr(repository, "calls")]


def _repository_call_counts(setup: TurnSetup) -> list[int]:
    return [len(repository.calls) for repository in _repositories(setup)]


def _new_repository_calls(setup: TurnSetup, calls_before: list[int]) -> list[str]:
    """Calls served during this turn only; fakes are reused across attempts."""
    return [
        call
        for repository, start in zip(_repositories(setup), calls_before, strict=True)
        for call in repository.calls[start:]
    ]
