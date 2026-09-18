class AuthError(Exception):
    """Base exception for the auth bounded context."""


class InvalidCredentials(AuthError):
    """Raised when an email/password pair does not match a known user."""
