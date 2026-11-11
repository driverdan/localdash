"""Shared pieces of the API response models.

Response models live beside the code that produces them (`app/<pkg>/schemas.py`,
`app/timeseries_schemas.py`); this module holds only what they all share.

Datetime rule: every datetime the API produces is declared `IsoDateTime`, which
serialises with Python's own `datetime.isoformat()`. That keeps the wire format
the handlers emitted before response models existed: a numeric offset
(`+00:00` for the UTC values Postgres returns, never Pydantic's default `Z`)
and microseconds only when they are non-zero. Clients and tests compare these
strings, so a model must never change how a timestamp is written.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer

IsoDateTime = Annotated[datetime, PlainSerializer(lambda d: d.isoformat(), return_type=str)]


class ApiModel(BaseModel):
    """Base for response models: an unknown field is an error, not silently dropped."""

    model_config = ConfigDict(extra="forbid")
