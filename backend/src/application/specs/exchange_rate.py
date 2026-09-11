"""Reads over the quoted-rate log (W9 B1).

Ordered by the day the rate applies to and only then by when it was
entered: a manager correcting this morning's rate at noon writes a second
row for the same day, and that correction is the one in force.
"""

from application.common.specification import Specification
from domain.enums import RateKind
from infrastructure.persistence.tenant.models import ExchangeRateModel


class LatestRateFor(Specification[ExchangeRateModel]):
    """The rate in force for one kind; used with ``find_one``."""

    def __init__(self, kind: RateKind) -> None:
        super().__init__(ExchangeRateModel)
        self.kind = kind
        self.where(ExchangeRateModel.kind == kind.value)
        self.order(
            ExchangeRateModel.effective_on.desc(),
            ExchangeRateModel.set_at.desc(),
            ExchangeRateModel.id.desc(),
        )


class RateHistory(Specification[ExchangeRateModel]):
    """Every rate quoted for one kind, newest first."""

    def __init__(self, kind: RateKind) -> None:
        super().__init__(ExchangeRateModel)
        self.kind = kind
        self.where(ExchangeRateModel.kind == kind.value)
        self.order(
            ExchangeRateModel.effective_on.desc(),
            ExchangeRateModel.set_at.desc(),
            ExchangeRateModel.id.desc(),
        )
