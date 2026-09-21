"""D-58 / T-04-15 — the real CV cannot be committed, and the fixture carries no
reachable contact details.

Two structural controls, both tests rather than habits: the gitignore guard fails
if either CV volume entry disappears, and the fixture guard fails if any committed
address could ever resolve or any phone-number shape appears.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sanitize import EMAIL_RE, PHONE_RE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = PROJECT_ROOT / ".gitignore"
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cv" / "awesomecv_standin.yaml"

#: The two volumes that hold the human's real CV data (D-58). Same class as `.env`.
REQUIRED_IGNORE_ENTRIES = ("cv/", "artifacts/")


def _missing_volume_entries(gitignore_text: str) -> list[str]:
    """Which required volume entries are absent from a gitignore text."""
    entries = {line.strip() for line in gitignore_text.splitlines()}
    return [entry for entry in REQUIRED_IGNORE_ENTRIES if entry not in entries]


def test_the_cv_and_artifacts_volumes_are_gitignored() -> None:
    missing = _missing_volume_entries(GITIGNORE.read_text(encoding="utf-8"))

    assert missing == [], (
        f"{missing} missing from .gitignore — the first broad `git add` would "
        "commit the user's real CV"
    )


def test_the_gitignore_guard_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    stripped = GITIGNORE.read_text(encoding="utf-8")
    stripped = "\n".join(
        line for line in stripped.splitlines() if line.strip() not in REQUIRED_IGNORE_ENTRIES
    )

    assert _missing_volume_entries(stripped) == list(REQUIRED_IGNORE_ENTRIES)


def test_the_committed_fixture_carries_no_reachable_contact_details() -> None:
    """Every address must be `.invalid`; no phone-number shape may appear at all.

    The check is shaped this way rather than banning the address pattern: the
    fixture legitimately needs a contact block to exercise the ``meta.contact``
    path, and a reserved-TLD-only rule is the *stronger* constraint — it admits a
    synthetic address while making a real mailbox impossible to commit.
    """
    text = FIXTURE.read_text(encoding="utf-8")

    addresses = EMAIL_RE.findall(text)
    assert addresses, "the fixture lost its contact block — the guard is vacuous"
    for address in addresses:
        assert address.endswith(".invalid"), (
            f"committed fixture carries a resolvable address: {address!r}"
        )

    phones = PHONE_RE.findall(text)
    assert phones == [], f"committed fixture carries a phone-number shape: {phones}"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
