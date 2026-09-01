"""Curated list of real phone models, seeded into a tenant's ``products``.

Only phones live here on purpose: customers, suppliers and prices differ
per store, so ``apexwms seed-phones`` fills the one table whose contents
are the same for everyone. Prices are left unset — the store enters them
at intake or by hand.

The SKU for a model is derived deterministically (``sku_for``) so a
re-run collides on the unique SKU and skips instead of duplicating.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects import SKU

_SKU_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")


@dataclass(frozen=True, slots=True)
class PhoneSpec:
    brand: str
    model: str
    storage_gb: int

    @property
    def name(self) -> str:
        return f"{self.brand} {self.model} {self.storage_gb}GB"

    @property
    def model_label(self) -> str:
        return f"{self.model} {self.storage_gb}GB"


def sku_for(spec: PhoneSpec) -> str:
    raw = f"{spec.brand}-{spec.model}-{spec.storage_gb}".upper().replace("+", "-PLUS-")
    out: list[str] = []
    for ch in raw:
        out.append(ch if ch in _SKU_ALLOWED else "-")
    collapsed = "-".join(part for part in "".join(out).split("-") if part)
    return collapsed[: SKU.MAX_LENGTH].rstrip("-")


def _variants(brand: str, model: str, storages: tuple[int, ...]) -> list[PhoneSpec]:
    return [PhoneSpec(brand, model, gb) for gb in storages]


_APPLE: list[PhoneSpec] = [
    *_variants("Apple", "iPhone 12", (64, 128, 256)),
    *_variants("Apple", "iPhone 13", (128, 256, 512)),
    *_variants("Apple", "iPhone 14", (128, 256, 512)),
    *_variants("Apple", "iPhone 14 Plus", (128, 256)),
    *_variants("Apple", "iPhone 14 Pro", (128, 256, 512)),
    *_variants("Apple", "iPhone 14 Pro Max", (256, 512, 1024)),
    *_variants("Apple", "iPhone 15", (128, 256, 512)),
    *_variants("Apple", "iPhone 15 Plus", (128, 256)),
    *_variants("Apple", "iPhone 15 Pro", (128, 256, 512)),
    *_variants("Apple", "iPhone 15 Pro Max", (256, 512, 1024)),
    *_variants("Apple", "iPhone 16", (128, 256, 512)),
    *_variants("Apple", "iPhone 16 Pro", (128, 256, 512)),
    *_variants("Apple", "iPhone 16 Pro Max", (256, 512, 1024)),
    *_variants("Apple", "iPhone SE (2022)", (64, 128, 256)),
]

_SAMSUNG: list[PhoneSpec] = [
    *_variants("Samsung", "Galaxy S22", (128, 256)),
    *_variants("Samsung", "Galaxy S23", (128, 256)),
    *_variants("Samsung", "Galaxy S23 Ultra", (256, 512)),
    *_variants("Samsung", "Galaxy S24", (128, 256)),
    *_variants("Samsung", "Galaxy S24 Ultra", (256, 512, 1024)),
    *_variants("Samsung", "Galaxy S25", (128, 256)),
    *_variants("Samsung", "Galaxy S25 Ultra", (256, 512)),
    *_variants("Samsung", "Galaxy Z Flip5", (256, 512)),
    *_variants("Samsung", "Galaxy Z Fold5", (256, 512)),
    *_variants("Samsung", "Galaxy A15", (128, 256)),
    *_variants("Samsung", "Galaxy A25", (128, 256)),
    *_variants("Samsung", "Galaxy A35", (128, 256)),
    *_variants("Samsung", "Galaxy A55", (128, 256)),
    *_variants("Samsung", "Galaxy A05s", (64, 128)),
]

_XIAOMI: list[PhoneSpec] = [
    *_variants("Xiaomi", "13T", (256,)),
    *_variants("Xiaomi", "13T Pro", (256, 512)),
    *_variants("Xiaomi", "14", (256, 512)),
    *_variants("Xiaomi", "14T Pro", (256, 512)),
    *_variants("Xiaomi", "Redmi Note 12", (128, 256)),
    *_variants("Xiaomi", "Redmi Note 13", (128, 256)),
    *_variants("Xiaomi", "Redmi Note 13 Pro", (256, 512)),
    *_variants("Xiaomi", "Redmi Note 14", (128, 256)),
    *_variants("Xiaomi", "Redmi Note 14 Pro", (256, 512)),
    *_variants("Xiaomi", "Redmi 13C", (128, 256)),
    *_variants("Xiaomi", "Redmi 14C", (128, 256)),
    *_variants("Xiaomi", "Poco X6 Pro", (256, 512)),
    *_variants("Xiaomi", "Poco X7 Pro", (256, 512)),
    *_variants("Xiaomi", "Poco F6", (256, 512)),
]

_OTHER: list[PhoneSpec] = [
    *_variants("Google", "Pixel 7", (128, 256)),
    *_variants("Google", "Pixel 8", (128, 256)),
    *_variants("Google", "Pixel 8 Pro", (128, 256, 512)),
    *_variants("Google", "Pixel 9", (128, 256)),
    *_variants("Google", "Pixel 9 Pro", (128, 256, 512)),
    *_variants("OnePlus", "11", (128, 256)),
    *_variants("OnePlus", "12", (256, 512)),
    *_variants("OnePlus", "12R", (128, 256)),
    *_variants("OnePlus", "Nord 4", (128, 256)),
    *_variants("Realme", "12 Pro", (128, 256)),
    *_variants("Realme", "12 Pro+", (256, 512)),
    *_variants("Realme", "C67", (128, 256)),
    *_variants("Honor", "90", (256, 512)),
    *_variants("Honor", "Magic6 Lite", (128, 256)),
    *_variants("Honor", "X9b", (256,)),
    *_variants("Infinix", "Note 40", (128, 256)),
    *_variants("Infinix", "Hot 40i", (128, 256)),
    *_variants("Tecno", "Camon 30", (128, 256)),
    *_variants("Tecno", "Spark 20 Pro", (128, 256)),
]

PHONES: tuple[PhoneSpec, ...] = (*_APPLE, *_SAMSUNG, *_XIAOMI, *_OTHER)
