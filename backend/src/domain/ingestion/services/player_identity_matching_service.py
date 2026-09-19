"""Matches synthetic WC2026 roster players against real Transfermarkt player
candidates using a 3-tier confidence cascade:

- `EXACT_NAME_DOB` (1.000): normalized full name AND date of birth match.
- `EXACT_NAME_TEAM` (0.950): normalized full name matches, DOB missing or
  mismatched, but the synthetic player's national team resolves to the
  candidate's `current_national_team_id`.
- `FUZZY_NAME` ([0.850, 0.949)): `rapidfuzz.fuzz.WRatio` name similarity,
  scaled into the tier range. Below 0.850 emits no candidate.

Pure function, no DB/HTTP -- fully unit-testable with fixture player lists.

Deviation from the design's literal two-argument signature: matching the
`EXACT_NAME_TEAM` tier requires knowing which real `national_team_id`
corresponds to each synthetic player's `team_id`. The design left this
mapping's exact plumbing as an open item; this service accepts it as an
explicit `national_team_id_by_team_id` parameter (populated by
`RosterScopingService.resolve_national_teams`) rather than embedding team
lookups inside this otherwise-pure matching function.
"""

import unicodedata
from decimal import Decimal

from rapidfuzz import fuzz

from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import PlayerMatchMethod
from src.domain.players.model.player import Player

_FUZZY_FLOOR_SCORE = 85.0
_FUZZY_MIN_CONFIDENCE = Decimal("0.850")
_FUZZY_MAX_CONFIDENCE = Decimal("0.949")
_FUZZY_CONFIDENCE_SPAN = _FUZZY_MAX_CONFIDENCE - _FUZZY_MIN_CONFIDENCE


def _normalize_name(name: str) -> str:
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return " ".join(stripped.lower().split())


class PlayerIdentityMatchingService:
    def match(
        self,
        synthetic_players: list[Player],
        real_player_candidates: list[dict],
        national_team_id_by_team_id: dict[int, int],
    ) -> list[PlayerIdentityCandidate]:
        candidates: list[PlayerIdentityCandidate] = []
        for player in synthetic_players:
            match = self._match_one(player, real_player_candidates, national_team_id_by_team_id)
            if match is not None:
                candidates.append(match)
        return candidates

    def _match_one(
        self,
        player: Player,
        real_player_candidates: list[dict],
        national_team_id_by_team_id: dict[int, int],
    ) -> PlayerIdentityCandidate | None:
        normalized_player_name = _normalize_name(player.name)
        expected_national_team_id = national_team_id_by_team_id.get(player.team_id)

        best_fuzzy: tuple[dict, float] | None = None
        for real_candidate in real_player_candidates:
            real_full_name = f"{real_candidate['first_name']} {real_candidate['last_name']}"
            normalized_real_name = _normalize_name(real_full_name)

            if normalized_player_name == normalized_real_name:
                if real_candidate.get("date_of_birth") == player.date_of_birth:
                    return self._candidate(
                        player, real_candidate, PlayerMatchMethod.EXACT_NAME_DOB, Decimal("1.000")
                    )
                if (
                    expected_national_team_id is not None
                    and expected_national_team_id == real_candidate.get("current_national_team_id")
                ):
                    return self._candidate(
                        player, real_candidate, PlayerMatchMethod.EXACT_NAME_TEAM, Decimal("0.950")
                    )
                # Exact name, no DOB or team confirmation: fall through to
                # fuzzy scoring at maximum similarity rather than auto-accepting.
                score = 100.0
            else:
                score = fuzz.WRatio(normalized_player_name, normalized_real_name)

            if score >= _FUZZY_FLOOR_SCORE and (best_fuzzy is None or score > best_fuzzy[1]):
                best_fuzzy = (real_candidate, score)

        if best_fuzzy is None:
            return None
        real_candidate, score = best_fuzzy
        confidence = self._scale_fuzzy_confidence(score)
        return self._candidate(player, real_candidate, PlayerMatchMethod.FUZZY_NAME, confidence)

    def _scale_fuzzy_confidence(self, score: float) -> Decimal:
        ratio = Decimal(str(min(score, 100.0) - _FUZZY_FLOOR_SCORE)) / Decimal(
            str(100.0 - _FUZZY_FLOOR_SCORE)
        )
        confidence = _FUZZY_MIN_CONFIDENCE + ratio * _FUZZY_CONFIDENCE_SPAN
        return min(confidence, _FUZZY_MAX_CONFIDENCE).quantize(Decimal("0.001"))

    def _candidate(
        self,
        player: Player,
        real_candidate: dict,
        method: PlayerMatchMethod,
        confidence: Decimal,
    ) -> PlayerIdentityCandidate:
        return PlayerIdentityCandidate(
            player_id=player.id,
            real_player_id=real_candidate["player_id"],
            match_method=method,
            match_confidence=confidence,
        )
