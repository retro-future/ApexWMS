"""Why goods are coming back from a customer (PRD §5.4b, FR-4.9).

A closed set for the same reason ``SupplierReturnReason`` is one: the
question a store asks of its returns is *"what is coming back, and why"*,
and that has to group. ``OTHER`` is here because a set that cannot express
a real case forces the operator to pick a wrong one.

``WARRANTY`` is separate from ``DEFECTIVE`` even though both describe a
broken handset: one is a fault found at the counter within days, the other
a claim against a promise the store made, and an owner reading the report
wants to tell them apart.
"""

from enum import StrEnum


class CustomerReturnReason(StrEnum):
    DEFECTIVE = "defective"
    NOT_AS_EXPECTED = "not_as_expected"
    WRONG_ITEM = "wrong_item"
    WARRANTY = "warranty"
    OTHER = "other"
