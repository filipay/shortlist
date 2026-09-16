"""Jinja filters shared across the server-rendered UI.

These live in ``app/web/`` so the templates and the API fragments that render
them share one set of formatting rules. They are registered against every
``Jinja2Templates`` instance via ``app.web.template_env.make_templates``.
"""

from __future__ import annotations

from datetime import date, datetime

_LABELS: dict[str, str] = {
    # Rule kinds — readable names for criteria and exclusion chips.
    "salary_floor": "Salary floor",
    "exclude_keyword": "Exclude keyword",
    "location": "Location",
    "remote": "Remote",
    "seniority": "Seniority",
    "company_blocklist": "Company blocklist",
    # Run statuses — short, human verbs/adjectives.
    "done": "Finished",
    "running": "Running",
    "partial": "Partial",
    "failed": "Failed",
    # Triggers / reasons.
    "manual": "Manual",
    "unknown": "Unknown",
}

_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DATE_FORMAT = "%Y-%m-%d"


def human_label(value: str | None) -> str:
    """Map a machine enum to a short human label.

    Unknown values fall back to title-casing with underscores replaced by spaces,
    so ad-hoc rule kinds or future statuses still read cleanly.
    """
    if not value:
        return ""
    if value in _LABELS:
        return _LABELS[value]
    return value.replace("_", " ").strip().title()


def format_datetime(value: datetime | date | str | None) -> str:
    """Render one timestamp in the site's single format.

    Datetimes show ``YYYY-MM-DD HH:MM``; bare dates show ``YYYY-MM-DD``.
    ISO strings (e.g. from ``QueueRow.posted``) are parsed and reformatted.
    ``None`` becomes an em dash so unfinished states never look like a zero.
    """
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime(_DATETIME_FORMAT)
    if isinstance(value, date):
        return value.strftime(_DATE_FORMAT)
    if isinstance(value, str):
        if not value.strip():
            return "—"
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        return parsed.strftime(_DATETIME_FORMAT if "T" in value else _DATE_FORMAT)
    return str(value)
