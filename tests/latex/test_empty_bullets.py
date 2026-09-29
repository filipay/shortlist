r"""Renderer regression: an entry with ZERO bullets must not emit an empty itemize.

A real tailored CV failed to compile with::

    ! LaTeX Error: Something's wrong--perhaps a missing \item.
    l.136 \\end{itemize}

The Layer-1 ``bullet_conservation`` check explicitly passes "minus the declared
drops", so a patch may legitimately DropBullet *every* bullet of an entry. The
renderer previously emitted ``\\begin{itemize}`` unconditionally, so that
legitimate state produced ``\\begin{itemize}`` immediately followed by
``\\end{itemize}`` — an environment with no ``\\item``, which XeTeX rejects.

These assertions are on the rendered ``.tex``, not a PDF: there is no LaTeX
engine in the sandbox. Removing the ``\\BLOCK{ if entry.bullets }`` guard makes
``test_an_entry_with_no_bullets_emits_no_itemize`` fail.
"""

from __future__ import annotations

import pytest

from app.domain.cv import RenderPlan
from app.latex.render import render_plan_to_tex


def _plan(bullets: list[dict[str, str]]) -> RenderPlan:
    """One section, one entry, the supplied bullets (possibly none)."""
    return RenderPlan.model_validate(
        {
            "name": "Test Person",
            "sections": [
                {
                    "id": "sec.experience",
                    "title": "Experience",
                    "entries": [
                        {
                            "id": "exp/acme-ltd-2021",
                            "org": "Acme Ltd",
                            "title": "Engineer",
                            "dates": "2021--2024",
                            "bullets": bullets,
                        }
                    ],
                }
            ],
        }
    )


def test_an_entry_with_no_bullets_emits_no_itemize() -> None:
    """The all-bullets-dropped state renders, and renders as a bare header."""
    rendered = render_plan_to_tex(_plan([]))

    assert "\\begin{itemize}" not in rendered
    assert "\\end{itemize}" not in rendered
    assert "\\item " not in rendered
    # Graceful degradation, not a dropped entry: the header survives.
    assert "\\textbf{Acme Ltd} --- \\textit{Engineer}" in rendered

    # The predicate discriminates: the SAME builder with one bullet DOES emit it,
    # so the absence above is caused by the empty list, not a missing environment.
    with_bullet = render_plan_to_tex(
        _plan([{"id": "bul/acme-ltd-2021/1", "text": "Shipped the thing"}])
    )
    assert "\\begin{itemize}" in with_bullet
    assert "\\end{itemize}" in with_bullet


def test_an_entry_with_bullets_is_unchanged() -> None:
    """The positive case keeps the environment, its item count and its close."""
    rendered = render_plan_to_tex(
        _plan(
            [
                {"id": "bul/1", "text": "First"},
                {"id": "bul/2", "text": "Second"},
            ]
        )
    )

    assert rendered.count("\\begin{itemize}") == 1
    assert rendered.count("\\item ") == 2
    assert rendered.count("\\end{itemize}") == 1
    assert "\\begin{itemize}[leftmargin=1.2em,itemsep=1pt]" in rendered
    assert "\\item First" in rendered
    assert "\\item Second" in rendered


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
