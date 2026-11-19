class DomainError(Exception):
    """Base exception for domain business rule violations."""


class DuplicateTransactionError(DomainError):
    """Raised when SHA-256 idempotency hash matches an existing transaction."""

    def __init__(self, idempotency_hash: str) -> None:
        self.idempotency_hash = idempotency_hash
        super().__init__(f"Transacción duplicada ignorada (hash={idempotency_hash[:12]}...)")


class UnauthorizedError(DomainError):
    """Raised when authentication credentials or device token are invalid."""


class ForbiddenError(DomainError):
    """Raised when an authenticated user lacks permissions for an operation."""


class ResourceNotFoundError(DomainError):
    """Raised when a requested domain entity does not exist."""


class SetupAlreadyCompletedError(DomainError):
    """Raised if initial administrator setup is invoked when users already exist."""
