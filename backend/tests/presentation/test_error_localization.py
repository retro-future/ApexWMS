import json

from starlette.requests import Request

from application.errors import ApplicationError, InvalidCredentialsError
from domain.errors import DomainError, PriceNotSetError, WrongLocationError
from presentation.errors import _handle


def _request(accept_language: str | None) -> Request:
    headers = [(b"accept-language", accept_language.encode())] if accept_language else []
    return Request({"type": "http", "headers": headers})


async def _detail(exc: Exception, accept_language: str | None) -> str:
    response = await _handle(_request(accept_language), exc)
    return json.loads(bytes(response.body))["detail"]


async def test_catalogued_error_is_localized() -> None:
    assert await _detail(InvalidCredentialsError(), "ru") == "Неверная почта или пароль."


async def test_error_params_are_interpolated_into_the_localized_template() -> None:
    detail = await _detail(
        WrongLocationError("english fallback", imei="356938035643809", number="INV-7"),
        "ru",
    )
    assert "356938035643809" in detail
    assert "INV-7" in detail
    assert "английском" not in detail  # the fallback string is not used


async def test_unknown_accept_language_uses_the_default_locale() -> None:
    detail = await _detail(InvalidCredentialsError(), "fr")
    assert "parol" in detail  # the Uzbek default


async def test_no_accept_language_uses_the_default_locale() -> None:
    detail = await _detail(InvalidCredentialsError(), None)
    assert "parol" in detail


async def test_uncatalogued_code_uses_the_exception_message() -> None:
    detail = await _detail(PriceNotSetError("this line has no price to sell at"), "ru")
    assert detail == "this line has no price to sell at"


async def test_price_not_set_is_localized() -> None:
    """Regression: PriceResolver used to build the whole sentence itself
    and raise with no key, so this always fell through to the English
    fallback regardless of locale."""
    detail = await _detail(
        PriceNotSetError(
            "english fallback",
            key="price_not_set_condition",
            imei="356938035643809",
            condition="used",
            sku="IP15P-256",
        ),
        "ru",
    )
    assert "356938035643809" in detail
    assert "английском" not in detail  # the fallback string is not used


def test_every_user_facing_error_has_a_code() -> None:
    def subclasses(base: type) -> set[type]:
        found: set[type] = set()
        for child in base.__subclasses__():
            found.add(child)
            found |= subclasses(child)
        return found

    for cls in subclasses(DomainError) | subclasses(ApplicationError):
        assert cls.code and cls.code.islower(), cls.__name__

    codes = [c.code for c in subclasses(DomainError) | subclasses(ApplicationError)]
    assert len(codes) == len(set(codes)), "duplicate error codes"
