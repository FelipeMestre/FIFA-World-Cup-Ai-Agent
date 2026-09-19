"""Contract for streaming Transfermarkt CSV tables. Implementations must
never materialize a full source file in memory -- source tables like
`games.csv`/`appearances.csv` are large before roster scoping filters them
down, so callers stream and filter row-by-row.
"""

from collections.abc import AsyncIterator
from typing import Protocol


class TransfermarktClientInterface(Protocol):
    def stream_csv_rows(self, table_name: str) -> AsyncIterator[dict[str, str]]:
        """Streams `{table_name}.csv.gz` rows as raw string-valued dicts
        (matching `TableIngestionSpec.column_spec`'s expected input shape).
        Raises `TransfermarktSourceUnavailableError` on a non-200 response.
        """
        ...
