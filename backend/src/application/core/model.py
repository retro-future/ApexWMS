"""The one place the camelCase wire-format convention is configured.

``Result``/``Command``/``Query`` inherit this instead of repeating the
same ``model_config`` in three places. Every payload class used as the
``TData`` of a ``ResultWithData``/``PagedResult`` must inherit it too —
the outer alias_generator does not cascade into a nested model's own
fields (pydantic resolves aliases per-model, not transitively).
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        protected_namespaces=(),
    )
