from datetime import date

from src.domain.ingestion.services import csv_parsers


def test_parse_date_accepts_a_bare_iso_date():
    assert csv_parsers.parse_date("2010-06-26") == date(2010, 6, 26)


def test_parse_date_accepts_a_full_timestamp():
    # Real Transfermarkt export (players.csv date_of_birth) carries a full
    # timestamp rather than a bare date -- verified against the live file.
    assert csv_parsers.parse_date("1978-06-09 00:00:00") == date(1978, 6, 9)


def test_parse_optional_date_accepts_a_full_timestamp():
    assert csv_parsers.parse_optional_date("1978-06-09 00:00:00") == date(1978, 6, 9)


def test_parse_optional_date_returns_none_for_blank_value():
    assert csv_parsers.parse_optional_date("") is None
