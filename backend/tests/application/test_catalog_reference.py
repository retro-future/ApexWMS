"""Locations and customers — FR-2.2.

Two of the three reference lists a store builds before it can receive or
sell anything. Names are unique for locations and deliberately not for
customers (PRD §4.2: two people share a name). Suppliers, the third, moved
to ``tests/api/test_catalog_api.py`` when they moved to the
specification-based repository.
"""

import pytest

from application.commands.create_customer import CreateCustomerCommand
from application.commands.create_location import CreateLocationCommand
from application.commands.update_customer import UpdateCustomerCommand
from application.commands.update_location import UpdateLocationCommand
from application.errors import DuplicateNameError, NotFoundError
from application.queries.get_customer import GetCustomerQuery
from application.queries.get_location import GetLocationQuery
from application.queries.list_customers import ListCustomersQuery
from application.queries.list_locations import ListLocationsQuery
from tests.application.builders import make_world


class TestLocations:
    async def test_create_trims_the_name_and_starts_active(self):
        world = make_world()

        result = await world.create_location().handle(
            CreateLocationCommand(name="  Warehouse ")
        )

        assert result.data.name == "Warehouse"
        assert result.data.is_active is True
        assert world.uow.commits == 1

    async def test_a_duplicate_name_is_refused(self):
        """Provisioning already seeded one; two rows called "Warehouse"
        would make every movement's location column ambiguous."""
        world = make_world()
        await world.create_location().handle(CreateLocationCommand(name="Warehouse"))

        with pytest.raises(DuplicateNameError):
            await world.create_location().handle(CreateLocationCommand(name="Warehouse"))

        assert len(world.locations.by_id) == 1
        assert world.uow.commits == 1

    async def test_renaming_onto_another_locations_name_is_refused(self):
        world = make_world()
        await world.create_location().handle(CreateLocationCommand(name="Warehouse"))
        second = await world.create_location().handle(CreateLocationCommand(name="Kiosk"))

        with pytest.raises(DuplicateNameError):
            await world.update_location().handle(
                UpdateLocationCommand(location_id=second.data.id, name="Warehouse")
            )

    async def test_a_location_can_keep_its_own_name_while_being_deactivated(self):
        world = make_world()
        created = await world.create_location().handle(
            CreateLocationCommand(name="Warehouse")
        )

        result = await world.update_location().handle(
            UpdateLocationCommand(
                location_id=created.data.id, name="Warehouse", is_active=False
            )
        )

        assert result.data.is_active is False
        assert await world.locations.get(created.data.id) is not None

    async def test_get_raises_for_an_unknown_id(self):
        world = make_world()

        with pytest.raises(NotFoundError):
            await world.get_location().handle(GetLocationQuery(location_id=world.tenant.id))

    async def test_list_pages_oldest_first(self):
        world = make_world()
        for name in ("Main Store", "Warehouse", "Kiosk"):
            await world.create_location().handle(CreateLocationCommand(name=name))

        page = await world.list_locations().handle(
            ListLocationsQuery(page=1, page_size=2)
        )

        assert [loc.name for loc in page.data] == ["Main Store", "Warehouse"]
        assert page.total_items == 3


class TestCustomers:
    async def test_two_customers_may_share_a_name(self):
        """Refusing the second Aziz Karimov at the till would be absurd."""
        world = make_world()

        first = await world.create_customer().handle(
            CreateCustomerCommand(full_name="Aziz Karimov", phone="+998901111111")
        )
        second = await world.create_customer().handle(
            CreateCustomerCommand(full_name="Aziz Karimov", phone="+998902222222")
        )

        assert first.data.id != second.data.id
        assert len(world.customers.by_id) == 2

    async def test_a_customer_carries_no_balance(self):
        """Debt is derived from invoices and payments (PRD §4.7), so there
        is no field here that could drift from the ledger."""
        world = make_world()

        result = await world.create_customer().handle(
            CreateCustomerCommand(full_name="Aziz Karimov")
        )

        assert set(result.data.model_dump()) == {"id", "full_name", "phone", "is_active"}

    async def test_a_phone_number_is_optional(self):
        world = make_world()

        result = await world.create_customer().handle(
            CreateCustomerCommand(full_name="Walk-in")
        )

        assert result.data.phone is None

    async def test_correcting_a_phone_number(self):
        world = make_world()
        created = await world.create_customer().handle(
            CreateCustomerCommand(full_name="Aziz Karimov", phone="+998901111111")
        )

        result = await world.update_customer().handle(
            UpdateCustomerCommand(customer_id=created.data.id, phone="+998902222222")
        )

        assert result.data.phone == "+998902222222"

    async def test_deactivating_preserves_the_row(self):
        world = make_world()
        created = await world.create_customer().handle(
            CreateCustomerCommand(full_name="Aziz Karimov")
        )

        result = await world.update_customer().handle(
            UpdateCustomerCommand(customer_id=created.data.id, is_active=False)
        )

        assert result.data.is_active is False
        assert await world.customers.get(created.data.id) is not None

    async def test_get_raises_for_an_unknown_id(self):
        world = make_world()

        with pytest.raises(NotFoundError):
            await world.get_customer().handle(GetCustomerQuery(customer_id=world.tenant.id))

    async def test_list_searches_by_phone_which_is_what_a_seller_has(self):
        world = make_world()
        await world.create_customer().handle(
            CreateCustomerCommand(full_name="Aziz Karimov", phone="+998901111111")
        )
        await world.create_customer().handle(
            CreateCustomerCommand(full_name="Nodira Yusupova", phone="+998902222222")
        )

        found = await world.list_customers().handle(ListCustomersQuery(search="902222222"))

        assert [c.full_name for c in found.data] == ["Nodira Yusupova"]
