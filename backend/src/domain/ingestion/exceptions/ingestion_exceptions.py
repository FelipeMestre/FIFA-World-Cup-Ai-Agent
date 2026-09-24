class IngestionError(Exception):
    """Base exception for the ingestion bounded context."""


class IngestionValidationError(IngestionError):
    """Raised when a source row fails column parsing/validation. Carries the
    row index and column name so a failure can be pinpointed in the source
    file -- no row is silently skipped.
    """


class UnknownTableError(IngestionError):
    """Raised when an ingestion target table name is not recognized."""


class InvalidJobTransitionError(IngestionError):
    """Raised when an `IngestionJob` status transition is not valid from its
    current status (e.g. `mark_running()` on an already-`succeeded` job).
    """


class IdentityLinkNotFoundError(IngestionError):
    """Raised when a `player_identity_link` id does not exist."""


class IdentityLinkAlreadyReviewedError(IngestionError):
    """Raised when approving/rejecting a link that is not currently `pending`."""


class RealPlayerNotFoundError(IngestionError):
    """Raised when a `real_player` id used as a reassignment target does not exist."""


class RealPlayerAlreadyLinkedError(IngestionError):
    """Raised when reassigning a `player_identity_link` to a `real_player` id
    already claimed by a different link -- `real_player_id` is unique.
    """


class TransfermarktSourceUnavailableError(IngestionError):
    """Raised by the Transfermarkt HTTP client on a non-200 response, or when
    the source is otherwise unreachable.
    """
