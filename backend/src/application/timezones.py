"""IANA timezone validation, shared by tenant creation and tenant settings.

Month-end period math runs in the tenant's timezone (FR-10.8), so an
invalid zone stored today is a silently wrong report later — reject it
at write time.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.errors import InvalidTimezoneError


def validate_timezone(timezone: str) -> str:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise InvalidTimezoneError(f"not an IANA timezone: {timezone!r}") from None
    return timezone
