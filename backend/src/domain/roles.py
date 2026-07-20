"""User roles within a tenant (PRD §2).

The permission matrix (§2.1) is not hierarchical — a Storekeeper can
receive goods but not sell, a Seller can sell but not receive — so
authorization checks name the allowed roles explicitly rather than
comparing rank.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STOREKEEPER = "storekeeper"
    SELLER = "seller"
