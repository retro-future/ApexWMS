"""Shared building blocks for the data-access layer: the repository ports,
the mapper port, and the specification objects use cases hand to a
repository."""

from application.common.mapper import EntityMapper
from application.common.repository import (
    MasterDbRepository,
    Repository,
    TenantDbRepository,
)
from application.common.specification import Specification

__all__ = [
    "EntityMapper",
    "MasterDbRepository",
    "Repository",
    "Specification",
    "TenantDbRepository",
]
