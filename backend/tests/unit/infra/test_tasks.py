"""Guards the synthetic-upload task's CSV parsing against a regression back
to the filesystem-path bug: the API and worker run in separate containers,
so the job payload must carry the file's bytes, never a local path.
"""

from src.infra.task_queue.tasks import _parse_csv_rows


def test_parse_csv_rows_reads_header_and_data_rows_from_bytes():
    csv_bytes = b"team_id,team_name\n1,Testland\n2,Otherland\n"

    rows = _parse_csv_rows(csv_bytes)

    assert rows == [
        {"team_id": "1", "team_name": "Testland"},
        {"team_id": "2", "team_name": "Otherland"},
    ]


def test_parse_csv_rows_handles_empty_body():
    assert _parse_csv_rows(b"team_id,team_name\n") == []
