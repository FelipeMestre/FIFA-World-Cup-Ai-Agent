"""Contract test for `_HttpxTransfermarktClient`: verifies HTTP behavior
(gzip CSV parsing, non-200 handling) via a real `httpx.AsyncClient` bound to
`httpx.MockTransport` -- exercises the client under test's own request/parse
path, not a mock of the class itself.
"""

import csv
import gzip
import io

import httpx
import pytest

from src.domain.ingestion.exceptions.ingestion_exceptions import (
    TransfermarktSourceUnavailableError,
)
from src.infra.transfermarkt.client import _HttpxTransfermarktClient


def _gzip_csv(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return gzip.compress(buffer.getvalue().encode("utf-8"))


@pytest.mark.asyncio
async def test_stream_csv_rows_yields_parsed_rows() -> None:
    fixture_rows = [
        {"club_id": "1", "name": "Real Madrid"},
        {"club_id": "2", "name": "Barcelona"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/data/clubs.csv.gz"
        return httpx.Response(200, content=_gzip_csv(fixture_rows))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = _HttpxTransfermarktClient(
            base_url="https://example.test/data", http_client=http_client
        )
        rows = [row async for row in client.stream_csv_rows("clubs")]

    assert rows == fixture_rows


@pytest.mark.asyncio
async def test_stream_csv_rows_raises_on_non_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = _HttpxTransfermarktClient(
            base_url="https://example.test/data", http_client=http_client
        )
        with pytest.raises(TransfermarktSourceUnavailableError):
            async for _ in client.stream_csv_rows("clubs"):
                pass
