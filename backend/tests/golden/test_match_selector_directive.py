"""Golden cases for the match-selector chip directive (`ChatService._build_match_directive`).

The directive is the imperative system message injected when the user pins a match; it must
name the exact tool arguments so the pinned fixture resolves to one match.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.services.chat_service import ChatService
from src.domain.chat.tools.registry import ToolDefinition
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.postgres.repositories.match_repository import get_match_repository
from src.infra.postgres.repositories.national_team_repository import get_national_team_repository
from tests.golden import fixture_matches
from tests.golden.tools import call_tool

_UNKNOWN_MATCH_ID = 995_999


@pytest.fixture
def chat_service(golden_session: AsyncSession) -> ChatService:
    """Real repositories; the directive builder never touches the cache or the LLM client."""
    return ChatService(
        conversation_cache=None,
        openrouter_client=None,
        tool_registry={},
        conversation_repo=get_conversation_repository(golden_session),
        chat_message_repo=get_chat_message_repository(golden_session),
        match_repo=get_match_repository(golden_session),
        national_team_repo=get_national_team_repository(golden_session),
        session=golden_session,
    )


async def test_directive_names_teams_date_and_the_tool_to_call(chat_service: ChatService) -> None:
    directive = await chat_service._build_match_directive(
        {"match_id": fixture_matches.GROUP_VLD_KRS_ID}
    )

    assert directive is not None
    assert "Valdoria vs Karsovia on 2026-06-14" in directive
    assert "You MUST call the get_match_analysis tool" in directive
    assert 'home_team_name="Valdoria"' in directive
    assert 'away_team_name="Karsovia"' in directive
    assert 'date="2026-06-14"' in directive


async def test_directive_uses_the_recorded_home_and_away_order(chat_service: ChatService) -> None:
    directive = await chat_service._build_match_directive(
        {"match_id": fixture_matches.FINAL_KRS_VLD_ID}
    )

    assert directive is not None
    assert "Karsovia vs Valdoria on 2026-07-19" in directive
    assert 'home_team_name="Karsovia"' in directive
    assert 'date="2026-07-19"' in directive


async def test_directive_arguments_resolve_the_pinned_match_even_when_teams_met_twice(
    chat_service: ChatService, registry: dict[str, ToolDefinition]
) -> None:
    """Valdoria and Karsovia met twice; the date in the directive is what disambiguates."""
    directive = await chat_service._build_match_directive(
        {"match_id": fixture_matches.FINAL_KRS_VLD_ID}
    )
    assert directive is not None

    outcome = await call_tool(
        registry,
        "get_match_analysis",
        home_team_name="Karsovia",
        away_team_name="Valdoria",
        date="2026-07-19",
    )

    assert outcome.payload["id"] == str(fixture_matches.FINAL_KRS_VLD_ID)
    assert "candidates" not in outcome.payload


@pytest.mark.parametrize(
    "context",
    [None, {}, {"match_id": None}, {"match_id": _UNKNOWN_MATCH_ID}],
    ids=["no-context", "empty-context", "null-match-id", "unknown-match-id"],
)
async def test_directive_is_absent_without_a_resolvable_match(
    chat_service: ChatService, context: dict | None
) -> None:
    assert await chat_service._build_match_directive(context) is None
