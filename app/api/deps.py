"""The auth seam (D-21).

Every route declares `user: User = Depends(current_user)`. Authentik OIDC later
replaces ONLY this function's body — route signatures do not change. There are
deliberately no `user_id` columns in v1.
"""

from __future__ import annotations

from app.config import settings
from app.domain.models import User

LOCAL_USER = User(id=settings.local_user_id, name="Local", email=None)


async def current_user() -> User:
    """v1: the single local user. Later: OIDC/Authentik via authlib.

    ROUTE SIGNATURES DO NOT CHANGE: the OIDC implementation replaces only the
    body of this function (ARCHITECTURE §11.1).
    """
    return LOCAL_USER
