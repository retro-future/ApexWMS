"""The two rates a phone store quotes (W9 §4).

Buying used stock and selling it are quoted at different rates, and the
spread between them is itself earnings. One rate would book every used
handset at the selling rate and understate what the intake was worth.
"""

from enum import StrEnum


class RateKind(StrEnum):
    SALE = "sale"
    BUYBACK = "buyback"
