"""Pure domain types.

`User` is the type the auth seam returns. v1 has a single local user; the OIDC
implementation later replaces only `current_user()`'s body.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """A user of the tool. `email` is optional because no auth exists in v1."""

    id: str
    name: str
    email: str | None = None
