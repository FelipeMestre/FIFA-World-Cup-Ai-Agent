import logging
import math
from collections.abc import Callable

import tiktoken

from src.infra.tokens.interfaces.token_counter_interface import TokenCounterInterface

logger = logging.getLogger(__name__)

ENCODING_NAME = "o200k_base"
FALLBACK_CHARS_PER_TOKEN = 4


def _load_default_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


class _TiktokenTokenCounter:
    """Counts tokens with tiktoken's `o200k_base` encoding.

    The encoding is loaded lazily on first use. `tiktoken` downloads the
    vocabulary on first load, so it can fail offline; in that case this
    degrades (fail-soft, once, with a warning) to `ceil(len(text) / 4)`
    rather than breaking chat. The count only drives history windowing, so
    an approximation is acceptable.
    """

    def __init__(
        self, encoding_loader: Callable[[], tiktoken.Encoding] = _load_default_encoding
    ) -> None:
        self._encoding_loader = encoding_loader
        self._encoding: tiktoken.Encoding | None = None
        self._encoding_unavailable = False

    def count_tokens(self, text: str) -> int:
        encoding = self._get_encoding()
        if encoding is None:
            return math.ceil(len(text) / FALLBACK_CHARS_PER_TOKEN)
        return len(encoding.encode(text, disallowed_special=()))

    def _get_encoding(self) -> tiktoken.Encoding | None:
        if self._encoding is not None:
            return self._encoding
        if self._encoding_unavailable:
            return None
        try:
            self._encoding = self._encoding_loader()
        except Exception:
            self._encoding_unavailable = True
            logger.warning(
                "Could not load tiktoken encoding %s; falling back to ceil(len/%d) token estimates",
                ENCODING_NAME,
                FALLBACK_CHARS_PER_TOKEN,
                exc_info=True,
            )
        return self._encoding


_default_token_counter = _TiktokenTokenCounter()


def get_token_counter() -> TokenCounterInterface:
    return _default_token_counter
