"""The M2 catalog's domain rules: SKU, Barcode, and Product's invariants.

Pure Python, no I/O — a value object that needs a database to know whether
it is valid is the wrong design (PRD §7.3).
"""

from datetime import UTC, datetime

import pytest

from domain.entities import Product
from domain.enums import TrackingType
from domain.errors import (
    BarcodeNotAllowedError,
    CurrencyMismatchError,
    InvalidBarcodeError,
    InvalidMoneyError,
    InvalidSkuError,
)
from domain.value_objects import SKU, Barcode, Currency, Money

# Real EAN-13 / UPC-A / EAN-8 codes, check digits included.
VALID_EAN13 = "4006381333931"
VALID_UPC_A = "036000291452"
VALID_EAN8 = "96385074"


def make_product(**overrides) -> Product:
    tracking = overrides.pop("tracking_type", TrackingType.SERIAL)
    fields = {
        "sku": SKU("IP15P-256"),
        "name": "iPhone 15 Pro 256GB",
        "tracking_type": tracking,
        "currency": Product.default_currency_for(tracking),
        "is_active": True,
        "created_at": datetime(2026, 7, 1, tzinfo=UTC),
    }
    return Product(**{**fields, **overrides})


class TestSku:
    def test_parse_trims_and_upper_cases(self):
        assert SKU.parse("  ip15p-256 ").value == "IP15P-256"

    def test_two_spellings_of_one_code_are_the_same_value(self):
        """Frozen dataclass equality is what stops "sku-1" and "SKU-1"
        becoming two catalog rows."""
        assert SKU.parse("case-clear") == SKU.parse("CASE-CLEAR")

    @pytest.mark.parametrize("raw", ["", "   ", "A" * 65, "IP 15", "CAFÉ", "SKU#1"])
    def test_rejects_unusable_codes(self, raw: str):
        with pytest.raises(InvalidSkuError):
            SKU.parse(raw)

    def test_rejects_a_non_string(self):
        with pytest.raises(InvalidSkuError):
            SKU.parse(12345)  # type: ignore[arg-type]


class TestBarcode:
    @pytest.mark.parametrize("code", [VALID_EAN13, VALID_UPC_A, VALID_EAN8])
    def test_accepts_valid_ean_and_upc(self, code: str):
        assert Barcode(code).value == code

    def test_parse_tolerates_scanner_separators(self):
        assert Barcode.parse(" 4 006381-333931 ").value == VALID_EAN13

    def test_rejects_a_wrong_check_digit(self):
        """A single mistyped digit is exactly what the check digit exists
        to catch — the same reasoning as IMEI's Luhn (PRD §4.2)."""
        with pytest.raises(InvalidBarcodeError):
            Barcode("4006381333932")

    @pytest.mark.parametrize("raw", ["", "123", "40063813339311", "400638133393X"])
    def test_rejects_malformed_codes(self, raw: str):
        with pytest.raises(InvalidBarcodeError):
            Barcode.parse(raw)


class TestCurrencyDefaults:
    def test_a_phone_defaults_to_usd_and_an_accessory_to_som(self):
        """FR-2.6, and the reason the default lives in domain: no call site
        has to remember which way round it goes."""
        assert Product.default_currency_for(TrackingType.SERIAL) is Currency.USD
        assert Product.default_currency_for(TrackingType.QUANTITY) is Currency.UZS


class TestProductInvariants:
    def test_a_quantity_product_may_carry_a_barcode(self):
        product = make_product(
            tracking_type=TrackingType.QUANTITY, barcode=Barcode(VALID_EAN13)
        )
        assert product.barcode == Barcode(VALID_EAN13)

    def test_a_serial_product_may_not(self):
        """FR-2.3: a phone is identified by its IMEI, not by an EAN."""
        with pytest.raises(BarcodeNotAllowedError):
            make_product(tracking_type=TrackingType.SERIAL, barcode=Barcode(VALID_EAN13))

    def test_the_sale_price_must_be_in_the_products_own_currency(self):
        """The 100x corruption bug, refused structurally: a som price on a
        dollar product cannot be constructed at all (PRD §11)."""
        with pytest.raises(CurrencyMismatchError):
            make_product(
                tracking_type=TrackingType.SERIAL,
                default_sale_price=Money.from_major("50000", Currency.UZS),
            )

    def test_the_sale_price_may_not_be_negative(self):
        with pytest.raises(InvalidMoneyError):
            make_product(default_sale_price=Money(-1, Currency.USD))

    def test_a_product_may_be_unpriced(self):
        assert make_product().default_sale_price is None

    def test_two_products_with_the_same_attributes_are_not_equal(self):
        """Identity is the id, not the attributes (PRD §7.6) — two boxes of
        the same case are still two catalog rows if someone made two."""
        assert make_product() != make_product()

    def test_uzs_and_usd_prices_do_not_share_an_exponent(self):
        """FR-2.9, at the point it actually matters: the same major amount
        on a phone and on an accessory stores two different integers."""
        phone = make_product(default_sale_price=Money.from_major("1000", Currency.USD))
        case = make_product(
            tracking_type=TrackingType.QUANTITY,
            default_sale_price=Money.from_major("1000", Currency.UZS),
        )
        assert phone.default_sale_price.amount_minor == 100_000
        assert case.default_sale_price.amount_minor == 1_000
