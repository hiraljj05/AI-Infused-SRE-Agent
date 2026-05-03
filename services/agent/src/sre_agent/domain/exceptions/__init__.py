class DomainError(Exception):
    """Base class for domain-level errors (business rule violations)."""


class IncidentStateError(DomainError):
    """Raised when an operation is invalid for the incident's current state."""


class ApprovalStateError(DomainError):
    """Raised when an approval operation is invalid for the saga's current state."""


class GuardrailViolation(DomainError):
    """Raised when an action would violate a configured guardrail."""


class NotAuthorized(DomainError):
    """Raised when the principal is not authorized to perform the action."""


class ConfigurationError(DomainError):
    """Raised when a domain-level configuration is invalid or missing."""
