import json

from starlette.requests import Request

from application.errors import ApplicationError, InvalidCredentialsError
from domain.errors import DomainError, InsufficientStockError
from presentation.errors import _handle


def _request(accept_language: str | None) -> Request:
    headers = [(b"accept-language", accept_language.encode())] if accept_language else []
    return Request({"type": "http", "headers": headers})


async def _detail(exc: Exception, accept_language: str | None) -> str:
    response = await _handle(_request(accept_language), exc)
    return json.loads(bytes(response.body))["detail"]


async def test_catalogued_error_is_localized() -> None:
    assert await _detail(InvalidCredentialsError(), "ru") == "Неверная почта или пароль."


async def test_unknown_accept_language_uses_the_default_locale() -> None:
    assert await _detail(InvalidCredentialsError(), "fr") == "Email yoki parol noto'g'ri."


async def test_no_accept_language_uses_the_default_locale() -> None:
    assert await _detail(InvalidCredentialsError(), None) == "Email yoki parol noto'g'ri."


async def test_uncatalogued_code_uses_the_exception_message() -> None:
    detail = await _detail(InsufficientStockError("holds 2, wanted 5"), "ru")
    assert detail == "holds 2, wanted 5"


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
