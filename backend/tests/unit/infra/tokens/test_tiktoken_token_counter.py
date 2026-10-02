import logging

import tiktoken

from src.infra.tokens.repositories.tiktoken_token_counter import (
    FALLBACK_CHARS_PER_TOKEN,
    _TiktokenTokenCounter,
)


def _unloadable_encoding():
    raise OSError("cannot download o200k_base while offline")


def test_counts_tokens_with_the_o200k_base_encoding() -> None:
    counter = _TiktokenTokenCounter()
    expected = len(tiktoken.get_encoding("o200k_base").encode("Who won the 2022 World Cup?"))

    assert counter.count_tokens("Who won the 2022 World Cup?") == expected


def test_empty_text_counts_zero_tokens() -> None:
    assert _TiktokenTokenCounter().count_tokens("") == 0


def test_falls_back_to_chars_over_four_rounded_up_when_encoding_cannot_load(caplog) -> None:
    counter = _TiktokenTokenCounter(encoding_loader=_unloadable_encoding)

    with caplog.at_level(logging.WARNING):
        assert counter.count_tokens("a" * 9) == 3  # ceil(9 / 4)
        assert counter.count_tokens("a" * 8) == 2
        assert counter.count_tokens("") == 0

    assert FALLBACK_CHARS_PER_TOKEN == 4


def test_fallback_logs_a_single_warning_not_one_per_call(caplog) -> None:
    counter = _TiktokenTokenCounter(encoding_loader=_unloadable_encoding)

    with caplog.at_level(logging.WARNING):
        counter.count_tokens("abc")
        counter.count_tokens("def")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
