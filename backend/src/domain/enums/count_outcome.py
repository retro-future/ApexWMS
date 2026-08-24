"""How one handset fared in a physical count (PRD §5.6, FR-6.3).

The vocabulary of the three lists a closed count reports. Derived from two
facts and never stored: whether the opening snapshot expected the unit, and
whether anyone scanned it.

``UNEXPECTED`` covers both a handset the system thought was elsewhere and
an IMEI it has no row for at all — the second is what FR-6.4b's unpriced
surprise unit comes from.
"""

from enum import StrEnum


class CountOutcome(StrEnum):
    MATCHED = "matched"
    MISSING = "missing"
    UNEXPECTED = "unexpected"
