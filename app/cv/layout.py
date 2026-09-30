"""The remembered CV layout preference — one token beside ``cv.yaml``.

A layout is not a ranking weight and not part of the fact store, so it gets its own
one-token file (``layout``) in the same CV volume the fact store lives in, rather
than a new table, a migration or a Settings field. This module is deliberately
IO-only: validation is against the key set the renderer actually ships
(:data:`app.latex.render.LAYOUTS`), and it never renders anything.

Fail closed, always. A missing or unreadable file, an unknown token or a hand-edited
value all resolve to :data:`app.latex.render.DEFAULT_LAYOUT` (Classic), and a write
of an unknown token is refused outright — a bad preference can never break a render.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.latex.render import DEFAULT_LAYOUT, LAYOUTS

#: The preference document's filename inside the CV volume.
LAYOUT_FILENAME = "layout"


def read_layout(cv_dir: str | Path) -> str:
    """The stored layout token, or the Classic default.

    Total: a missing file, an unreadable file, an empty value or an unknown token is
    the default, never an exception.
    """
    path = Path(cv_dir) / LAYOUT_FILENAME
    try:
        token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        # `UnicodeDecodeError` is a `ValueError`, not an `OSError`: a non-UTF-8
        # preference file must still fail closed to Classic, never raise.
        return DEFAULT_LAYOUT
    return token if token in LAYOUTS else DEFAULT_LAYOUT


def write_layout(cv_dir: str | Path, layout: str) -> None:
    """Persist ``layout`` atomically, or refuse an unknown token with ``ValueError``.

    The token is stripped and validated against the shipped key set; an unknown
    value raises before anything is written. The write is a temp file in the
    destination's own directory followed by :func:`os.replace`, so a reader ever sees
    either the old token or the new one, never a partial file — and a failed write
    leaves no temp file behind.
    """
    token = layout.strip() if isinstance(layout, str) else ""
    if token not in LAYOUTS:
        raise ValueError(f"unknown CV layout {layout!r}; expected one of {sorted(LAYOUTS)}")

    directory = Path(cv_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / LAYOUT_FILENAME
    fd, temp_name = tempfile.mkstemp(dir=directory, prefix=".layout-", suffix=".tmp")
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{token}\n")
        os.replace(temp, destination)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


__all__ = ["LAYOUT_FILENAME", "read_layout", "write_layout"]
