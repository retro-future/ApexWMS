"""What state a handset is in (PRD §4.2, §4.5b).

Not decoration, and not a description: ``condition`` is a **pricing
input**. It is the single field that decides whether a unit may inherit
its model's catalog price (FR-2.14), and getting it wrong is the
difference between a used iPhone quoted at what it is worth and the same
handset quoted at the new price of $900 with nothing on screen to say so.

Only ``NEW`` inherits. Everything else carries its own price or cannot be
sold — see ``domain/services/pricing.py``.
"""

from enum import StrEnum


class DeviceCondition(StrEnum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"
