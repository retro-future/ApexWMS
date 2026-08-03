"""A repository base is a convenience, not a classification of tables.

Four tenant bases grew here once, because every table that did not fit the
existing ones was answered with a *new sibling* — and a hierarchy that has
to have a box for every table must grow with every table. The rule that
replaced it: an aggregate that does not fit ``TenantCrudRepository``
inherits ``TenantRepository`` and writes the methods its port declares. It
does not get a base of its own.

That rule is the kind of thing prose forgets, so it is a test. If a fifth
milestone's document repository needs something the two bases do not give,
the answer is to widen ``SqlRepository``'s mechanics or to write the method
locally — not to add a third base and edit the tuple below.

Pure reflection over the repository modules: no database, no Docker.
"""

import inspect

import infrastructure.persistence.master.repositories as master_repositories
import infrastructure.persistence.tenant.repositories as tenant_repositories
from infrastructure.persistence.master.repositories.base import MasterCrudRepository
from infrastructure.persistence.repository import CrudRepository, SqlRepository
from infrastructure.persistence.tenant.repositories.base import (
    TenantCrudRepository,
    TenantRepository,
)

TENANT_BASES = (TenantCrudRepository, TenantRepository)
MASTER_BASES = (MasterCrudRepository,)


def _repositories(module) -> list[type]:
    return [
        member
        for name, member in inspect.getmembers(module, inspect.isclass)
        if name.startswith("Sql")
    ]


class TestOneBasePerDatabase:
    def test_every_tenant_repository_uses_one_of_the_two_tenant_bases(self):
        for repository in _repositories(tenant_repositories):
            bases = [base for base in TENANT_BASES if issubclass(repository, base)]
            assert len(bases) == 1, (
                f"{repository.__name__} inherits {bases or 'no tenant base'}; it must "
                "inherit exactly one of TenantCrudRepository (a one-row "
                "TenantActivatableRow aggregate) or TenantRepository (everything else)"
            )

    def test_every_master_repository_uses_the_master_base(self):
        for repository in _repositories(master_repositories):
            assert issubclass(repository, MASTER_BASES), (
                f"{repository.__name__} must inherit MasterCrudRepository, so its "
                "constructor demands a MasterSession"
            )


class TestNoThirdBase:
    """The guard proper: no new abstract base has appeared under either package."""

    def test_tenant_package_exports_exactly_its_two_bases(self):
        exported = {
            name
            for name in tenant_repositories.__all__
            if name.endswith("Repository") and not name.startswith("Sql")
        }
        assert exported == {"TenantCrudRepository", "TenantRepository"}

    def test_the_bases_descend_from_one_root(self):
        """One place holds the session and the read/write mechanics.

        Two roots is how the duplicated ``add`` (identical body, identical
        comment, two branches of the tree) happened last time.
        """
        for base in (*TENANT_BASES, *MASTER_BASES, CrudRepository):
            assert issubclass(base, SqlRepository)


class TestLedgersHaveNoUpdate:
    """The append-only rule lives in the port, and the SQL classes honour it.

    ``AppendOnlyRepository`` (application/ports/repository.py) is what
    handlers depend on, so it is what actually prevents editing history.
    This checks the implementations did not casually inherit an ``update``
    back in — which is what a shared CRUD base would have done.
    """

    def test_append_only_repositories_expose_no_update(self):
        append_only = (
            tenant_repositories.SqlStockMovementRepository,
            tenant_repositories.SqlFinancialTransactionRepository,
            tenant_repositories.SqlProductPriceChangeRepository,
            tenant_repositories.SqlDeviceUnitPriceChangeRepository,
        )
        for repository in append_only:
            assert not hasattr(repository, "update"), (
                f"{repository.__name__} has an update(): a ledger row is corrected by "
                "appending its compensation (PRD §4.3 rule 2), never by editing"
            )
