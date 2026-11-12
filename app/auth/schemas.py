"""Response models for the auth API (/api/v1/auth); see app/contracts.py."""

from __future__ import annotations

import uuid

from app.contracts import ApiModel


class UserOut(ApiModel):
    """The signed-in user as `/auth/me` returns it; never carries the password hash."""

    id: uuid.UUID
    email: str
    is_superuser: bool
