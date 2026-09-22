"""Read model for the `get_player_comparison` chat tool.

Mirrors the frontend's `PlayerComparison` contract (frontend/src/features/
chat/types.ts) field-for-field: attributes are snake_case Python, but every
model reuses `player_analysis`'s `_CamelModel` base so
`PlayerComparison.model_dump(mode="json", by_alias=True)` produces the exact
camelCase shape `CompareWidgetPart.data` expects on the wire, with no
reshaping at the tool-handler boundary -- same convention as `PlayerAnalysis`.

`ComparisonRowData.note`/`playerAPercentile`/`playerBPercentile` are typed
optional (`?:`) rather than nullable (`| null`) on the frontend side, but
this codebase's established convention (see `PlayerStatRow.percentile`) is
to always send the key with an explicit JSON `null` rather than omit it, so
`model_dump` is called the same way here -- no `exclude_none`.
"""

from typing import Literal

from src.domain.player_analytics.model.player_analysis import _CamelModel

Normalization = Literal["per90", "totals"]


class ComparisonPlayerRef(_CamelModel):
    id: str
    initials: str
    name: str
    team_code: str
    position: Literal["GK", "DEF", "MID", "FWD"]
    minutes: int


class ComparisonRowData(_CamelModel):
    label: str
    note: str | None = None
    player_a_value: str
    player_b_value: str
    player_a_is_better: bool
    player_b_is_better: bool
    player_a_percentile: int | None = None
    player_b_percentile: int | None = None


class PlayerComparison(_CamelModel):
    id: str
    normalization: Normalization
    scope_label: str
    player_a: ComparisonPlayerRef
    player_b: ComparisonPlayerRef
    rows: list[ComparisonRowData]
    insights: list[str]
    min_minutes_caption: str
