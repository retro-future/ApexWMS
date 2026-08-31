"""What each report may be ordered by (PRD §5.9).

``PagedQuery`` deliberately has no generic ``order_by``: a free-text sort
column is either a whitelist repeated in every repository or an injection
hole. Each report names its own fixed set here instead, in one place the
query, the port and the statement that implements it all import, so the
three cannot drift.
"""

from enum import StrEnum


class DeviationSort(StrEnum):
    CONFIRMED_AT = "confirmed_at"
    APPROVER = "approver"
    CUSTOMER = "customer"


class AgeingSort(StrEnum):
    """No margin option, deliberately. Ordering a mixed list numerically by
    ``asking − cost`` would compare som against cents, which is the one
    comparison §4.5 rule 4 exists to prevent."""

    AGE = "age"
    MARKDOWNS = "markdowns"


class BelowCostSort(StrEnum):
    SHORTFALL = "shortfall"
    SKU = "sku"
