"""CQRS core primitives — mirrors domain/core's role for the application layer."""

from application.core.cqrs import Command, PagedQuery, Query
from application.core.handler import IRequestHandler
from application.core.model import CamelModel
from application.core.request import IRequest
from application.core.results import PagedResult, Result, ResultWithData

__all__ = [
    "CamelModel",
    "Command",
    "IRequest",
    "IRequestHandler",
    "PagedQuery",
    "PagedResult",
    "Query",
    "Result",
    "ResultWithData",
]
