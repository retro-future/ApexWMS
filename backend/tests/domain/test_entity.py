"""Entity identity semantics (PRD §7.6): identity is the id, not the attributes."""

from datetime import UTC, datetime
from uuid import uuid4

from domain.core import MasterEntity, TenantEntity
from domain.entities import Employee, Tenant, User
from domain.enums import TenantRole, TenantStatus

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def make_user(**overrides) -> User:
    defaults = {
        "email": "a@example.com",
        "full_name": "A",
        "password_hash": None,
                "is_active": True,
        "created_at": NOW,
    }
    return User(**(defaults | overrides))


class TestIdentityEquality:
    def test_same_id_different_attributes_are_equal(self):
        # The guard: this is the case that fails the moment a subclass forgets
        # `eq=False` and dataclass regenerates field-wise equality. (The
        # different-ids case below passes under both semantics, so it proves
        # nothing on its own.)
        shared = uuid4()
        assert make_user(id=shared, email="a@example.com") == make_user(
            id=shared, email="renamed@example.com"
        )

    def test_identical_attributes_different_ids_are_not_equal(self):
        assert make_user(id=uuid4()) != make_user(id=uuid4())

    def test_different_types_sharing_an_id_are_not_equal(self):
        shared = uuid4()
        user = make_user(id=shared)
        tenant = Tenant(id=shared, name="A", slug="a", status=TenantStatus.ACTIVE, created_at=NOW)
        assert user != tenant

    def test_entity_is_not_equal_to_an_unrelated_object(self):
        assert make_user() != "not an entity"


class TestHashing:
    def test_usable_as_a_set_member(self):
        shared = uuid4()
        assert len({make_user(id=shared), make_user(id=shared, full_name="B")}) == 1

    def test_mutating_a_non_id_field_does_not_move_the_bucket(self):
        user = make_user()
        seen = {user}
        user.full_name = "Renamed"
        assert user in seen

    def test_same_id_across_types_hashes_differently(self):
        shared = uuid4()
        user = make_user(id=shared)
        tenant = Tenant(id=shared, name="A", slug="a", status=TenantStatus.ACTIVE, created_at=NOW)
        assert len({user, tenant}) == 2


class TestIdentityGeneration:
    def test_id_is_minted_when_none_is_passed(self):
        assert make_user().id != make_user().id

    def test_explicit_id_is_preserved(self):
        given = uuid4()
        assert make_user(id=given).id == given


class TestDatabaseMarkers:
    def test_the_login_identity_is_master_side(self):
        user = make_user()
        assert isinstance(user, MasterEntity)
        assert not isinstance(user, TenantEntity)

    def test_a_presence_at_one_store_is_tenant_side(self):
        employee = Employee(
            email="a@example.com",
            full_name="A",
            role=TenantRole.OWNER,
            is_active=True,
            created_at=NOW,
        )
        assert isinstance(employee, TenantEntity)
        assert not isinstance(employee, MasterEntity)

    def test_tenants_are_marked_master_and_not_tenant(self):
        tenant = Tenant(
            id=uuid4(), name="A", slug="a", status=TenantStatus.ACTIVE, created_at=NOW
        )
        assert isinstance(tenant, MasterEntity)
        assert not isinstance(tenant, TenantEntity)
