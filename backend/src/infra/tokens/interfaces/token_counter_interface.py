from typing import Protocol


class TokenCounterInterface(Protocol):
    def count_tokens(self, text: str) -> int: ...
