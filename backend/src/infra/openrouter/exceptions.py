class OpenRouterRequestFailed(Exception):
    """Raised when OpenRouter returns a non-2xx response or an unparsable payload."""

    def __init__(self, status_code: int | None, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenRouter request failed ({status_code}): {detail}")
