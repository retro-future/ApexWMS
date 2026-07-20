"""Shared entity foundations: identity, and which database an entity belongs to."""

from domain.core.entity import Entity, UuidEntity
from domain.core.markers import MasterEntity, TenantEntity

__all__ = ["Entity", "MasterEntity", "TenantEntity", "UuidEntity"]
