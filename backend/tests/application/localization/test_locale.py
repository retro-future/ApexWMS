import pytest

from application.localization.locale import Locale


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("ru", Locale.RU),
        ("ru-RU", Locale.RU),
        ("en-US,en;q=0.9", Locale.EN),
        ("uz", Locale.UZ),
        ("", Locale.UZ),
        (None, Locale.UZ),
        ("fr", Locale.UZ),
        ("  RU  ", Locale.RU),
    ],
)
def test_parse(header: str | None, expected: Locale) -> None:
    assert Locale.parse(header) is expected


def test_default_is_uz() -> None:
    assert Locale.DEFAULT is Locale.UZ


def test_iteration_yields_only_canonical_members() -> None:
    assert list(Locale) == [Locale.UZ, Locale.RU, Locale.EN]
