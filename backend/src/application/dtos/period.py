"""A reporting month, resolved to two instants — FR-10.8.

The tenant's timezone decides where a month starts and ends, so a sale at
23:30 on the 31st in Tashkent belongs to that month and not the next one.
``start`` and ``end`` are UTC because that is what the ledgers store;
``end`` is exclusive, matching ``totals_by_type``'s *until*.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Period:
    year: int
    month: int
    timezone: str
    start: datetime
    end: datetime
