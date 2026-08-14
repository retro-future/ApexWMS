"""Where a Goods Receipt's goods came from (PRD §4.4, FR-3.3b).

For used stock the answer is not "a supplier": handsets are bought from
walk-in customers, and a receipt for one names no supplier at all. The
alternative was a ``Supplier`` row called "Trade-in", which costs no schema
and makes the supplier report lie — turning *"what did we make on
trade-ins?"*, the question a store that buys used stock asks constantly,
into a filter on a supplier's **name**.

This says nothing about the goods themselves. ``condition`` is a fact about
each individual handset and the two never constrain each other: a supplier
delivers used phones, and a walk-in occasionally brings in a sealed one.
"""

from enum import StrEnum


class AcquisitionSource(StrEnum):
    SUPPLIER = "supplier"
    TRADE_IN = "trade_in"
