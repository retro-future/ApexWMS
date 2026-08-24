"""Why goods are going back to the supplier (PRD §5.5, FR-5.1).

A closed set rather than free text, because the month-end view of returns
is *"what are we sending back, and why"* — a question that has to group.
Whatever detail the reason does not carry goes in the document's ``note``,
which every document already has.

``OTHER`` is not one of FR-5.1's three. It is here because a closed set
that cannot express a real case forces the operator to pick a wrong one,
and a wrong reason is worse for the report than an unspecific one.
"""

from enum import StrEnum


class SupplierReturnReason(StrEnum):
    DEFECTIVE = "defective"
    UNSOLD = "unsold"
    WRONG_ITEM = "wrong_item"
    OTHER = "other"
