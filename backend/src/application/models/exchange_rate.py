"""One quoted rate on the wire (W9 B1).

``som_per_usd`` travels as a string, the way every price input already
does: a rate multiplies an amount, and a JSON number would hand the browser
a float to do it with.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from domain.entities import ExchangeRate
from domain.enums import RateKind


class ExchangeRateData(CamelModel):
    id: UUID
    kind: RateKind
    som_per_usd: str
    effective_on: date
    set_at: datetime
    user_id: UUID
    # Quoted for a day earlier than today, so the counter is working off a
    # figure nobody has confirmed this morning.
    is_stale: bool

    @classmethod
    def from_entity(cls, rate: ExchangeRate, today: date) -> ExchangeRateData:
        return cls(
            id=rate.id,
            kind=rate.kind,
            som_per_usd=cls.plain(rate.som_per_usd),
            effective_on=rate.effective_on,
            set_at=rate.set_at,
            user_id=rate.user_id,
            is_stale=rate.effective_on < today,
        )

    @staticmethod
    def plain(rate: Decimal) -> str:
        """12 500, not 12500.0000.

        The column keeps four decimal places whether or not a rate uses
        them, and a screen that echoes the padding back reads like a
        different number. ``normalize`` drops the padding but renders whole
        thousands in scientific notation, which the ``f`` format undoes.
        """
        return format(rate.normalize(), "f")
