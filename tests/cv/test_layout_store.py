"""260930-lay — the one-token CV layout preference file.

Reads are total and fail closed to Classic; writes validate against the renderer's
own key set and replace atomically, leaving no temp file behind.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cv.layout import LAYOUT_FILENAME, read_layout, write_layout
from app.latex.render import DEFAULT_LAYOUT, LAYOUTS


def test_a_written_layout_round_trips(tmp_path: Path) -> None:
    for layout in sorted(LAYOUTS):
        write_layout(tmp_path, layout)
        assert read_layout(tmp_path) == layout


def test_a_missing_file_is_classic(tmp_path: Path) -> None:
    assert read_layout(tmp_path / "does-not-exist") == DEFAULT_LAYOUT


def test_an_empty_file_is_classic(tmp_path: Path) -> None:
    (tmp_path / LAYOUT_FILENAME).write_text("", encoding="utf-8")

    assert read_layout(tmp_path) == DEFAULT_LAYOUT


def test_a_garbage_token_is_classic(tmp_path: Path) -> None:
    (tmp_path / LAYOUT_FILENAME).write_text("fancy\n", encoding="utf-8")

    assert read_layout(tmp_path) == DEFAULT_LAYOUT


def test_an_unreadable_path_is_classic(tmp_path: Path) -> None:
    """A directory where the file should be is an OSError, never a raise."""
    (tmp_path / LAYOUT_FILENAME).mkdir()

    assert read_layout(tmp_path) == DEFAULT_LAYOUT


def test_write_rejects_an_unknown_token_and_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_layout(tmp_path, "fancy")

    assert not (tmp_path / LAYOUT_FILENAME).exists()


def test_write_rejects_an_empty_token(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_layout(tmp_path, "")

    assert not (tmp_path / LAYOUT_FILENAME).exists()


def test_write_strips_surrounding_whitespace(tmp_path: Path) -> None:
    write_layout(tmp_path, "  modern\n")

    assert (tmp_path / LAYOUT_FILENAME).read_text(encoding="utf-8") == "modern\n"
    assert read_layout(tmp_path) == "modern"


def test_write_is_a_single_token_line(tmp_path: Path) -> None:
    write_layout(tmp_path, "compact")

    content = (tmp_path / LAYOUT_FILENAME).read_text(encoding="utf-8")

    assert content == "compact\n"


def test_an_atomic_rewrite_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    write_layout(tmp_path, "modern")
    write_layout(tmp_path, "compact")

    assert sorted(path.name for path in tmp_path.iterdir()) == [LAYOUT_FILENAME]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
