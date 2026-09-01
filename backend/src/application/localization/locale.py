"""The language a request is answered in.

Resolved from the ``Accept-Language`` header the BFF forwards from the
``apex_locale`` cookie. There is no per-user stored setting; the cookie is
the choice.
"""

from __future__ import annotations

from enum import StrEnum


class Locale(StrEnum):
    UZ = "uz"
    RU = "ru"
    EN = "en"

    DEFAULT = "uz"

    @classmethod
    def parse(cls, header: str | None) -> Locale:
        if not header:
            return cls.DEFAULT
        first = header.split(",")[0].strip().lower()
        tag = first.split(";")[0].strip().split("-")[0].strip()
        try:
            return cls(tag)
        except ValueError:
            return cls.DEFAULT
