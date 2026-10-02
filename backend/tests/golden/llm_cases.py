"""Layer B plumbing: a golden case is data (question + check), run through the real LLM.

Everything except the model is production: the real tool registry bound to the real
repositories on the seeded golden fixture, the real executor, system prompt and schemas.
The `golden_session` fixture keeps one `AsyncSession` open for the whole test, so every
attempt of a case (and every tool call inside a turn) reuses it.

Run (needs `OPENROUTER_API_KEY` and the local Postgres):

    cd backend && python -m pytest -m llm_eval tests/golden
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.services.chat_service import ChatService
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.postgres.repositories.match_analytics_repository import (
    get_match_analytics_repository,
)
from src.infra.postgres.repositories.match_repository import get_match_repository
from src.infra.postgres.repositories.national_team_repository import get_national_team_repository
from src.infra.postgres.repositories.player_analytics_repository import (
    get_player_analytics_repository,
)
from src.infra.postgres.repositories.team_analytics_repository import (
    get_team_analytics_repository,
)
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts


@dataclass(frozen=True)
class GoldenLlmCase:
    """One fixed question and the check its answer (and tool calls) must satisfy.

    `pinned_match_id` simulates the match-selector chip: the real directive for that
    fixture match is added as a second system message, exactly like `ChatService`.
    """

    case_id: str
    question: str
    check: Callable[[ObservedTurn], None]
    pinned_match_id: int | None = None


async def build_match_directive(session: AsyncSession, match_id: int) -> str:
    """The production chip directive for a fixture match (`ChatService._build_match_directive`)."""
    chat_service = ChatService(
        conversation_cache=None,
        openrouter_client=None,
        tool_registry={},
        conversation_repo=get_conversation_repository(session),
        chat_message_repo=get_chat_message_repository(session),
        match_repo=get_match_repository(session),
        national_team_repo=get_national_team_repository(session),
        session=session,
    )
    directive = await chat_service._build_match_directive({"match_id": match_id})
    assert directive is not None, f"fixture match {match_id} did not resolve to a directive"
    return directive


async def build_turn_setup(session: AsyncSession, case: GoldenLlmCase) -> TurnSetup:
    extra_messages = ()
    if case.pinned_match_id is not None:
        extra_messages = (await build_match_directive(session, case.pinned_match_id),)
    return TurnSetup(
        team_repo=get_team_analytics_repository(session),
        player_repo=get_player_analytics_repository(session),
        match_repo=get_match_analytics_repository(session),
        extra_system_messages=extra_messages,
    )


async def run_golden_case(session: AsyncSession, case: GoldenLlmCase) -> None:
    """Ask the real model `EVAL_ATTEMPTS` times; require `EVAL_MIN_PASSES` clean passes."""
    setup = await build_turn_setup(session, case)
    await passes_enough_attempts(case.question, setup, case.check)
