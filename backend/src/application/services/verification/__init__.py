"""Auditing what the ledgers imply against what the projections say.

*"The ledger is the source of truth; projections are always rebuildable"*
(PRD §11) is only worth anything if something actually rebuilds them. This
is that something — the service behind ``apexwms verify-projections``,
``apexwms verify-financials`` and ``apexwms verify-balances``.

Three checks, deliberately separate because they can fail for different
reasons, and one class each:

- **``ProjectionVerifier``** (``projections.py``) recomputes stock levels,
  device statuses and both price projections from their append-only
  sources (§4.3, §4.5b). A mismatch means something wrote a projection
  without writing the row behind it.
- **``LedgerReconciler``** (``reconciliation.py``) is FR-10.7's money-side
  analogue: on-hand inventory value recomputed from stock, **checked per
  currency** against what the financial ledger says the store should be
  holding. A mismatch means goods and money disagree, which the month-end
  report surfaces as an error and never silently reconciles.
- **``BalanceVerifier``** (``balances.py``) is the debt side (§4.7,
  FR-10.7b). Customer balances are *always* derived, so there is no cached
  projection to check them against — what it audits instead is that the two
  independent records of the same fact agree: the ``payments`` table and the
  money ledger's ``PAYMENT_RECEIVED`` rows.

Everything here is driven by ports, so all three are testable with fakes and
no database — which matters, because a verification routine that can only be
exercised against production is one nobody trusts.
"""

from application.services.verification.balances import BalanceVerifier
from application.services.verification.discrepancy import Discrepancy
from application.services.verification.projections import ProjectionVerifier
from application.services.verification.reconciliation import LedgerReconciler

__all__ = [
    "BalanceVerifier",
    "Discrepancy",
    "LedgerReconciler",
    "ProjectionVerifier",
]
