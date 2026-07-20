"""Tenant timezone settings — FR-10.8 depends on this being correct."""

import pytest

from application.errors import InvalidTimezoneError
from tests.application.builders import make_world


async def test_get_returns_the_seeded_timezone():
    world = make_world()

    assert await world.get_tenant_settings().execute() == "Asia/Tashkent"


async def test_update_stores_and_commits_a_valid_timezone():
    world = make_world()

    result = await world.update_tenant_settings().execute("Europe/Berlin")

    assert result == "Europe/Berlin"
    assert await world.get_tenant_settings().execute() == "Europe/Berlin"
    assert world.uow.commits == 1


@pytest.mark.parametrize("timezone", ["Mars/Olympus_Mons", "", "UTC+5", "not a zone"])
async def test_update_rejects_an_invalid_timezone_without_committing(timezone: str):
    world = make_world()

    with pytest.raises(InvalidTimezoneError):
        await world.update_tenant_settings().execute(timezone)

    assert await world.get_tenant_settings().execute() == "Asia/Tashkent"
    assert world.uow.commits == 0
