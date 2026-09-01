from starlette.requests import Request

from application.localization.locale import Locale
from infrastructure.localization.current_locale_accessor import CurrentLocaleAccessor


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({"type": "http", "headers": headers})


def test_reads_accept_language() -> None:
    acc = CurrentLocaleAccessor(_request([(b"accept-language", b"ru-RU")]))
    assert acc.get_locale() is Locale.RU


def test_defaults_when_absent() -> None:
    assert CurrentLocaleAccessor(_request([])).get_locale() is Locale.UZ
