"""What every audit in ``application/services/verification`` reports, in one shape.

The three verifiers check different things and share nothing else — but
``apexwms verify-*`` prints all of them the same way, so the record they
hand back is common.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Discrepancy:
    """One thing that does not add up, in terms an operator can act on."""

    subject: str
    expected: str
    found: str

    def __str__(self) -> str:
        return f"{self.subject}: ledger says {self.expected}, projection says {self.found}"
