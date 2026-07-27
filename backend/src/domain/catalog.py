"""How a product's stock is tracked (PRD §4.1).

One flag on ``Product`` decides which path every stock operation takes
from M3 onward:

- ``SERIAL`` — a phone. Every physical unit is its own ``DeviceUnit`` row
  with its own IMEI and its own acquisition cost. You do not have "3
  iPhone 15 Pro"; you have three specific handsets.
- ``QUANTITY`` — a case, a charger, a screen protector. Tracked as
  ``(product, location) → integer quantity``. Nobody serializes a box of
  200 screen protectors.

Both paths write to the same ledger, so this is a fork in *handling*, not
a fork in the model.
"""

from enum import StrEnum


class TrackingType(StrEnum):
    SERIAL = "serial"
    QUANTITY = "quantity"
