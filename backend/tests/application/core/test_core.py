"""Pins the bug fixes applied while porting the reference CQRS interfaces.

Each test documents the specific defect that would exist if a fix were
reverted, not just "the happy path works".
"""

import pytest
from pydantic import BaseModel, ValidationError

from application.core import (
    CamelModel,
    Command,
    IRequest,
    IRequestHandler,
    PagedQuery,
    PagedResult,
    Query,
    Result,
    ResultWithData,
)


class Payload(CamelModel):
    user_id: int
    is_active: bool


def test_command_and_query_subclasses_define_without_mro_error() -> None:
    """Reference `Command(BaseModel, IRequest[TResult])` crashed at class-body
    evaluation with a C3 MRO conflict, since IRequest already extends
    BaseModel. Defining a concrete subclass must not raise."""

    class Ping(Command[Result]):
        pass

    class Pong(Query[Result]):
        pass

    assert issubclass(Ping, IRequest)
    assert issubclass(Pong, IRequest)


async def test_handler_result_type_is_tied_to_its_request() -> None:
    class Ping(IRequest[Result]):
        pass

    class PingHandler(IRequestHandler[Result, Ping]):
        async def handle(self, request: Ping) -> Result:
            return Result.succeed("pong")

    result = await PingHandler().handle(Ping())
    assert result.success is True
    assert result.message == "pong"


def test_generic_factory_methods_enforce_the_parametrized_type() -> None:
    """Reference succeed_with_data/fail were @staticmethods referencing the
    class's own unparametrized generic name inside their body, so calling
    them through a parametrized alias silently bypassed validation (proved:
    ResultWithData[Payload].succeed_with_data(garbage_dict) used to succeed
    with data=garbage_dict instead of raising). classmethod + cls(...) fixes
    this — the caller's parametrization must now be honored."""

    with pytest.raises(ValidationError):
        ResultWithData[Payload].succeed_with_data({"not": "valid"})  # type: ignore[arg-type]

    result = ResultWithData[Payload].succeed_with_data(Payload(user_id=1, is_active=True))
    assert result.data == Payload(user_id=1, is_active=True)


def test_result_with_data_fail_needs_no_payload() -> None:
    """data was a required field with no default, so fail() couldn't be
    constructed without a dummy payload. Now Optional with default None."""

    result = ResultWithData[Payload].fail("boom")
    assert result.success is False
    assert result.data is None
    assert result.error == "boom"


def test_paged_query_rejects_non_positive_page_size() -> None:
    """PagedRequest had no lower bound on page/page_size, so page_size=0
    would reach PagedResult.succeed_with_data's ceil(items/page_size) and
    raise ZeroDivisionError instead of failing validation up front."""

    class ListItemsQuery(PagedQuery[PagedResult[Payload]]):
        pass

    with pytest.raises(ValidationError):
        ListItemsQuery(page_size=0)

    with pytest.raises(ValidationError):
        ListItemsQuery(page=0)

    query = ListItemsQuery()
    assert query.page == 1
    assert query.page_size == 10


def test_paged_result_succeed_with_data_computes_pages_count() -> None:
    result = PagedResult[Payload].succeed_with_data(
        data=[Payload(user_id=1, is_active=True)], page_index=1, page_size=10, items_count=25
    )
    assert result.pages_count == 3
    assert result.total_items == 25


def test_camel_model_round_trips_camel_and_snake_case() -> None:
    payload = Payload.model_validate({"userId": 5, "isActive": False})
    assert payload.user_id == 5

    payload_by_name = Payload.model_validate({"user_id": 5, "is_active": False})
    assert payload_by_name.user_id == 5

    assert payload.model_dump(by_alias=True) == {"userId": 5, "isActive": False}


def test_nested_payload_must_itself_be_a_camel_model_to_serialize_camel_case() -> None:
    """The outer alias_generator on Result/ResultWithData does not cascade
    into a nested payload's own fields — this is the hard rule (every TData
    must inherit CamelModel), pinned here so a future payload class that
    forgets it fails loudly in CI rather than silently shipping snake_case."""

    class PlainPayload(BaseModel):
        user_id: int

    result = ResultWithData[PlainPayload].succeed_with_data(PlainPayload(user_id=1))
    dumped = result.model_dump(by_alias=True)
    assert "user_id" in dumped["data"]
    assert "userId" not in dumped["data"]

    camel_result = ResultWithData[Payload].succeed_with_data(Payload(user_id=1, is_active=True))
    camel_dumped = camel_result.model_dump(by_alias=True)
    assert "userId" in camel_dumped["data"]
