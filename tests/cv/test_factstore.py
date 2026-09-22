"""D-66 — the fact store loads loudly, and never touches the human's document.

No defaults, no partial load, path-qualified failures; and a full cycle leaves
``base.tex`` byte-identical.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from app.cv import factstore
from app.cv.factstore import CvFactStoreError, load_facts
from app.domain.cv import apply_patch, find_duplicate_ids

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"


def _raw_fixture() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def _write(tmp_path: Path, data: dict, name: str = "cv.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Test 1: the committed fixture loads --------------------------------------


def test_the_committed_fixture_loads_with_the_pinned_shape() -> None:
    facts = load_facts(FIXTURE)

    assert facts.schema_version == 1
    assert facts.meta.contact is not None
    assert facts.meta.contact.email == "alex.example@example.invalid"
    assert facts.meta.contact.phone is None
    assert [section.title_key for section in sorted(facts.sections, key=lambda s: s.order)] == [
        "sec.experience",
        "sec.skills",
    ]
    assert find_duplicate_ids(facts) == []
    assert facts.orgs and facts.titles
    assert facts.sections[0].entries[0].bullets


# --- Tests 2-5: loud, path-qualified failures ---------------------------------


def test_an_unknown_key_raises_naming_its_path(tmp_path: Path) -> None:
    data = _raw_fixture()
    data["meta"]["bogus_key"] = "surprise"
    path = _write(tmp_path, data)

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(path)

    assert "bogus_key" in str(excinfo.value)
    assert str(path.resolve()) in str(excinfo.value)


def test_a_missing_required_bullet_field_raises_with_the_dotted_path(
    tmp_path: Path,
) -> None:
    data = _raw_fixture()
    del data["sections"][0]["entries"][0]["bullets"][0]["text"]
    path = _write(tmp_path, data)

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(path)

    assert "sections.0.entries.0.bullets.0.text" in str(excinfo.value)


def test_a_schema_version_mismatch_names_both_values(tmp_path: Path) -> None:
    data = _raw_fixture()
    data["schema_version"] = 2
    path = _write(tmp_path, data)

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(path)

    message = str(excinfo.value)
    assert "2" in message
    assert "1" in message


def test_a_missing_file_raises_with_the_resolved_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "cv.yaml"

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(missing)

    assert str(missing.resolve()) in str(excinfo.value)


def test_non_utf8_bytes_raise_the_path_qualified_fact_store_error(
    tmp_path: Path,
) -> None:
    """A file that exists but cannot be decoded is one typed, path-qualified error.

    The decode failure is preserved as the cause rather than escaping ``load_facts``
    raw, so every caller routes through the one fact-store boundary failure.
    """
    path = tmp_path / "cv.yaml"
    path.write_bytes(b"\xff\xfe\x00\x01 not utf-8")

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(path)

    assert str(path.resolve()) in str(excinfo.value)
    assert "unreadable" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, UnicodeError)


# --- Test 6: duplicate IDs ----------------------------------------------------


def test_duplicate_entry_ids_raise_naming_the_duplicate(tmp_path: Path) -> None:
    data = _raw_fixture()
    data["sections"][0]["entries"].append(dict(data["sections"][0]["entries"][0]))
    path = _write(tmp_path, data)

    with pytest.raises(CvFactStoreError) as excinfo:
        load_facts(path)

    assert "exp/northwind-labs-2021" in str(excinfo.value)


def test_the_uniqueness_gate_itself_can_fail() -> None:
    """The load-time gate is a real re-check, not dead code behind the model."""
    facts = load_facts(FIXTURE)
    facts.sections[0].entries.append(facts.sections[0].entries[0])

    with pytest.raises(CvFactStoreError) as excinfo:
        factstore._assert_ids_unique(facts)

    assert "exp/northwind-labs-2021" in str(excinfo.value)


# --- Test 7: nothing is default-filled ----------------------------------------


def test_a_removed_required_field_never_yields_a_value(tmp_path: Path) -> None:
    data = _raw_fixture()
    del data["sections"][0]["entries"][0]["start"]
    path = _write(tmp_path, data)

    with pytest.raises(CvFactStoreError):
        load_facts(path)


# --- Test 8: the human's document is byte-identical across a full cycle --------


def test_a_full_load_and_identity_patch_leaves_base_tex_byte_identical(
    tmp_path: Path,
) -> None:
    cv_dir = tmp_path / "cv"
    cv_dir.mkdir()
    base_tex = cv_dir / "base.tex"
    base_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\nReal CV\n\\end{document}\n",
        encoding="utf-8",
    )
    (cv_dir / "cv.yaml").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    before_hash = _sha256(base_tex)
    before_mtime = base_tex.stat().st_mtime_ns

    facts = load_facts(cv_dir / "cv.yaml")
    plan = apply_patch(facts)
    assert plan.sections

    assert _sha256(base_tex) == before_hash
    assert base_tex.stat().st_mtime_ns == before_mtime


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
