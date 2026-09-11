"""Both rates in force, for the dashboard card (W9 B1).

Either side is null while the store has never quoted that kind. That is a
real state on the first morning and the card has to render it, so it is not
an error.
"""

from __future__ import annotations

from datetime import date

from application.core import CamelModel
from application.models.exchange_rate import ExchangeRateData
from domain.entities import ExchangeRate


class CurrentRatesData(CamelModel):
    sale: ExchangeRateData | None = None
    buyback: ExchangeRateData | None = None
    today: date

    @classmethod
    def from_entity(
        cls,
        sale: ExchangeRate | None,
        buyback: ExchangeRate | None,
        today: date,
    ) -> CurrentRatesData:
        return cls(
            sale=None if sale is None else ExchangeRateData.from_entity(sale, today),
            buyback=(
                None if buyback is None else ExchangeRateData.from_entity(buyback, today)
            ),
            today=today,
        )
