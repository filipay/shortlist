"""CV-R7 — the preamble sanitiser comments unguarded pdfTeX-only primitives only.

Deliberately conservative: preamble-only, line-start-only, comments rather than
deletes, and never touches a primitive inside an ``\\if…``/``\\fi`` guard branch.
"""

from __future__ import annotations

import pytest

from app.domain.tex import sanitise_preamble

_MARKER = "% [pdftex-only, commented by shortlist]"

_PREAMBLE = r"""\documentclass{article}
\usepackage{fontspec}
\pdfminorversion 7
\ifx\pdfoutput\undefined
  \pdfpagewidth=8.5in
\fi
\ifnum\pdfoutput>0
  \pdfcompresslevel=9
\fi
\begin{document}
\pdfoutput=1
\end{document}
"""


def test_unguarded_preamble_primitives_are_commented_and_reported() -> None:
    tex, removed = sanitise_preamble(_PREAMBLE)

    assert removed == [r"\pdfminorversion"]
    assert f"{_MARKER} \\pdfminorversion 7" in tex
    # The line is commented, not deleted — the original command is still visible.
    assert r"\pdfminorversion 7" in tex


def test_guarded_primitives_are_left_alone() -> None:
    tex, removed = sanitise_preamble(_PREAMBLE)

    assert r"\pdfpagewidth=8.5in" in tex
    assert r"\pdfcompresslevel=9" in tex
    assert r"\pdfpagewidth" not in removed
    assert r"\pdfcompresslevel" not in removed
    # The guard-can-fail companion: the guarded lines are genuinely untouched.
    assert f"{_MARKER} \\pdfpagewidth" not in tex
    assert f"{_MARKER} \\pdfcompresslevel" not in tex


def test_the_document_body_is_left_alone() -> None:
    tex, removed = sanitise_preamble(_PREAMBLE)

    assert r"\pdfoutput=1" in tex
    assert f"{_MARKER} \\pdfoutput" not in tex
    assert r"\pdfoutput" not in removed


def test_a_preamble_without_primitives_is_unchanged() -> None:
    tex = r"\documentclass{article}" + "\n" + r"\begin{document}" + "\nx\n" + r"\end{document}\n"

    out, removed = sanitise_preamble(tex)

    assert out == tex
    assert removed == []


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
