"""Fixtures shared by the M3 API suites.

``owner`` lives here rather than in either module because both
``test_ledger_api.py`` and ``test_verify_cli.py`` need the same settled
store, and a fixture imported across test modules shadows itself.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD


@pytest.fixture
async def owner(create_tenant):
    """A provisioned store with its Owner logged in and past onboarding."""
    return await create_tenant(password=PASSWORD)
