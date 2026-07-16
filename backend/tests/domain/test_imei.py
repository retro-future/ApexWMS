import pytest

from domain.errors import InvalidIMEIError
from domain.value_objects import IMEI

# Luhn-valid 15-digit IMEIs (check digit correct).
VALID_IMEIS = [
    "490154203237518",
    "356938035643809",
]


class TestValidIMEI:
    @pytest.mark.parametrize("raw", VALID_IMEIS)
    def test_accepts_valid_imei(self, raw):
        assert IMEI(raw).value == raw

    def test_parse_strips_whitespace_and_separators(self):
        assert IMEI.parse(" 49-015420-323751-8 ").value == "490154203237518"

    def test_str_returns_digits(self):
        assert str(IMEI("490154203237518")) == "490154203237518"

    def test_value_equality(self):
        assert IMEI("490154203237518") == IMEI("490154203237518")


class TestInvalidIMEI:
    def test_wrong_check_digit_rejected(self):
        # Valid IMEI with last digit flipped — the typo the Luhn digit exists to catch.
        with pytest.raises(InvalidIMEIError):
            IMEI("490154203237519")

    def test_single_digit_typo_rejected(self):
        with pytest.raises(InvalidIMEIError):
            IMEI("490154203237418")

    def test_too_short_rejected(self):
        with pytest.raises(InvalidIMEIError):
            IMEI("49015420323751")

    def test_too_long_rejected(self):
        with pytest.raises(InvalidIMEIError):
            IMEI("4901542032375189")

    def test_non_digits_rejected(self):
        with pytest.raises(InvalidIMEIError):
            IMEI("49015420323751A")

    def test_unicode_digits_rejected(self):
        # Arabic-Indic digits pass str.isdigit(); they are not an IMEI.
        with pytest.raises(InvalidIMEIError):
            IMEI("٤90154203237518")

    def test_empty_rejected(self):
        with pytest.raises(InvalidIMEIError):
            IMEI("")
