"""What is left of the repository-base guard after the ADR 0007 conversion.

Every one-row aggregate reaches ``SqlAlchemyRepository`` and every ledger
reaches ``SqlAppendOnlyRepository``, each through a ``Specification``. The
per-database subclasses in ``infrastructure/persistence/repositories/`` add
only a narrowed constructor.

The rule worth keeping as a test: an append-only repository has no
``update`` and no ``delete`` — the *absence* of the methods, so a ledger
repo that type-checks physically has no way to edit history (§4.3 rule 2).

Pure reflection over the repository modules: no database, no Docker.
"""

from infrastructure.persistence.repositories import (
    MasterSqlRepository,
    SqlAlchemyRepository,
    SqlAppendOnlyRepository,
    TenantSqlAppendOnlyRepository,
    TenantSqlRepository,
)


class TestOneRootPerConcern:
    def test_every_repository_shares_one_pair_of_roots(self):
        assert issubclass(SqlAlchemyRepository, SqlAppendOnlyRepository)
        assert issubclass(TenantSqlRepository, SqlAlchemyRepository)
        assert issubclass(MasterSqlRepository, SqlAlchemyRepository)
        assert issubclass(TenantSqlAppendOnlyRepository, SqlAppendOnlyRepository)

    def test_the_append_only_generic_repository_cannot_write_history(self):
        """The append-only rule is the absence of the methods, not a raise:
        a ledger repo that type-checks physically has no way to edit a row."""
        for forbidden in ("update", "delete"):
            assert not hasattr(SqlAppendOnlyRepository, forbidden)
            assert not hasattr(TenantSqlAppendOnlyRepository, forbidden)
            assert hasattr(SqlAlchemyRepository, forbidden)
