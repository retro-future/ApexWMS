"""A generated file on its way from a handler to the response."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderedDocument:
    """Bytes and the two things a browser needs to save them.

    A frozen dataclass rather than a ``CamelModel``: even wrapped in a
    ``ResultWithData`` envelope on its way out of the handler, it is never
    itself returned to FastAPI for serialization — the route reads
    ``result.data`` and hands the browser a raw ``Response`` built from its
    bytes, so this has no wire shape to validate.
    """

    filename: str
    content_type: str
    content: bytes
