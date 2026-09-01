"""Localized message templates for error ``detail`` strings and printed
documents.

The backend owns the catalog and formats the final string (approach A):
the frontend keeps rendering whatever ``detail`` it receives, and the PDF
renderers ask the catalog for their fixed words. One TOML file per locale
under ``messages/``, two tables: ``[errors]`` keyed by an exception's
``code``, ``[documents]`` keyed by a renderer literal.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from application.localization.locale import Locale

_LOG = logging.getLogger(__name__)
_DEFAULT_ROOT = Path(__file__).parent / "messages"


class MessageCatalog:
    def __init__(self, root: Path | None = None) -> None:
        base = root or _DEFAULT_ROOT
        self._data: dict[Locale, dict[str, dict[str, str]]] = {}
        for locale in Locale:
            raw = tomllib.loads((base / f"{locale.value}.toml").read_text("utf-8"))
            self._data[locale] = {
                table: {key: str(value) for key, value in entries.items()}
                for table, entries in raw.items()
            }

    def render(
        self, locale: Locale, table: str, key: str, /, **params: object
    ) -> str | None:
        template = self._lookup(locale, table, key) or self._lookup(
            Locale.EN, table, key
        )
        if template is None:
            return None
        try:
            return template.format(**params)
        except (KeyError, IndexError):
            _LOG.warning("message %s.%s is missing a placeholder value", table, key)
            return template

    def keys(self, table: str) -> frozenset[str]:
        return frozenset(self._data[Locale.EN].get(table, {}))

    def locale_keys(self, locale: Locale, table: str) -> frozenset[str]:
        return frozenset(self._data.get(locale, {}).get(table, {}))

    def _lookup(self, locale: Locale, table: str, key: str) -> str | None:
        return self._data.get(locale, {}).get(table, {}).get(key)
