"""The shared SQLAlchemy declarative base.

Every model module (`app.models`, `app.news.models`, `app.events.models`)
registers its tables on `Base.metadata` when it is imported. This module
creates no engine and reads no settings, so importing a model has no side
effects beyond mapper registration.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
