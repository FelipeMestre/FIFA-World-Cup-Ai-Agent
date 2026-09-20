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

# Known WC2026 team_name -> Transfermarkt country_name mismatches that
# normalization (accents/case/whitespace) doesn't fix -- e.g. FIFA's
# official "IR Iran" vs Transfermarkt's plain "Iran". Keys and values are
# both pre-normalized. Add to this as more mismatches turn up; there's no
# way to derive these automatically, they're just known naming quirks.
_KNOWN_NAME_ALIASES: dict[str, str] = {
    "ir iran": "iran",
}


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
        normalized `fifa_code`/`team_name` against `country_name`, falling
        back to `_KNOWN_NAME_ALIASES` for a known mismatch neither catches.

        `wc2026_teams` must be genuine WC2026 teams only (`fifa_code` set)
        -- an auto-created Transfermarkt-only `NationalTeam` has no
        `fifa_code` to normalize.
        """
        by_name: dict[str, dict] = {
            _normalize(row["country_name"]): row for row in national_team_rows
        }
        result: dict[int, int] = {}
        for team in wc2026_teams:
            normalized_name = _normalize(team.name)
            real_team = (
                by_name.get(normalized_name)
                or by_name.get(_normalize(team.fifa_code))
                or by_name.get(_KNOWN_NAME_ALIASES.get(normalized_name, ""))
            )
            if real_team is not None:
                result[team.id] = real_team["national_team_id"]
        return result

    def national_team_ids(self, national_team_id_by_team_id: dict[int, int]) -> set[int]:
        return set(national_team_id_by_team_id.values())
