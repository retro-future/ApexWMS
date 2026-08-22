"""How the money physically arrived (PRD §4.7).

A **label**, not a processed transaction. The system records that a
customer handed over cash or that a transfer landed; it runs no card rails
and reconciles no till (PRD §1.4). Nothing branches on this value — it
exists so the owner can read their own history back.
"""

from enum import StrEnum


class PaymentMethod(StrEnum):
    CASH = "cash"
    TRANSFER = "transfer"
    CARD = "card"
