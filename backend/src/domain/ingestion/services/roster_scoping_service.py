"""Matches the synthetic WC2026 `team` roster against Transfermarkt
`national_teams.csv` rows to produce the team-level scope every subsequent
Transfermarkt pull is filtered against.

This is deliberately narrow: team-level scoping only. Player-level scoping is
a side effect of `PlayerIdentityMatchingService`'s own output (the matched/
auto-accepted candidate ids ARE the player scope) -- this service exists so
that scoping step can run first, since the player pull itself must already be
filtered by national team before identity matching sees it (per the data
flow: reference ingest -> team scoping -> player stream-filter -> identity
matching -> detail pulls).

Pure function, no DB/HTTP -- fully unit-testable with fixture rows.
"""

import unicodedata

from src.domain.national_teams.model.national_team import NationalTeam


def _normalize(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(stripped.lower().split())


class RosterScopingService:
    def resolve_national_teams(
        self,
        wc2026_teams: list[NationalTeam],
        national_team_rows: list[dict],
    ) -> dict[int, int]:
        """Returns `{synthetic team_id: real national_team_id}` for every
        synthetic team that resolves to a real national team, matched by
        normalized `fifa_code`/`team_name` against `country_name`.
        """
        by_name: dict[str, dict] = {
            _normalize(row["country_name"]): row for row in national_team_rows
        }
        result: dict[int, int] = {}
        for team in wc2026_teams:
            real_team = by_name.get(_normalize(team.name)) or by_name.get(
                _normalize(team.fifa_code)
            )
            if real_team is not None:
                result[team.id] = real_team["national_team_id"]
        return result

    def national_team_ids(self, national_team_id_by_team_id: dict[int, int]) -> set[int]:
        return set(national_team_id_by_team_id.values())
