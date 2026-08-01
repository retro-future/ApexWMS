"""Tenant slug validation.

The slug is how an anonymous login names its tenant (PRD §3.3), so it is
typed by a human and appears in an HTTP header. Restricting it to
lowercase letters, digits and single hyphens keeps it unambiguous and
leaves it usable as a DNS label if tenants ever move to subdomains.
"""

import re

from application.errors import InvalidSlugError


class SlugNormalizer:
    _SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    MAX_SLUG_LENGTH = 63  # A DNS label, so the subdomain door stays open.

    def normalize(self, slug: str) -> str:
        candidate = slug.strip().lower()
        if (
            not candidate
            or len(candidate) > self.MAX_SLUG_LENGTH
            or not self._SLUG.match(candidate)
        ):
            raise InvalidSlugError(
                f"not a valid tenant slug: {slug!r} "
                "(lowercase letters, digits and single hyphens)"
            )
        return candidate
