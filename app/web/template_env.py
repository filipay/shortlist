"""Shared Jinja template environment factory.

Every server-rendered surface (pages in ``app/web/routes.py`` and HTMX fragments
in ``app/api/*.py``) uses this factory so filters and global conventions stay in
one place.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.web import filters


def make_templates(directory: str | Path) -> Jinja2Templates:
    """A ``Jinja2Templates`` instance with the application's filters registered."""
    templates = Jinja2Templates(directory=str(directory))
    templates.env.filters["human_label"] = filters.human_label
    templates.env.filters["format_datetime"] = filters.format_datetime
    return templates
