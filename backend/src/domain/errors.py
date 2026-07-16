"""Domain errors.

Every rule violation inside the domain raises a subclass of DomainError.
The presentation layer maps these to HTTP responses; the domain knows
nothing about HTTP.
"""


class DomainError(Exception):
    """Base class for all domain rule violations."""


class InvalidMoneyError(DomainError):
    """Money constructed from something that is not an exact minor-unit amount."""


class CurrencyMismatchError(DomainError):
    """Arithmetic or comparison attempted across two different currencies."""


class InvalidIMEIError(DomainError):
    """A string that is not a structurally valid IMEI (length, digits, Luhn)."""
