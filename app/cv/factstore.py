"""The single reader of the machine-canonical CV document.

This module fails loudly and path-qualified. It never default-fills and never
partially loads, because a missing date quietly supplied by a default is invented
CV content (D-66). A missing file, a non-decodable or otherwise unreadable file,
invalid YAML, a schema-version mismatch, a duplicate fact id and a removed
required field are all the one ``CvFactStoreError`` type at this boundary, so
every caller (ranking now, tailoring later) sees a single typed failure.

It does not commit, write or cache anything. ``cv.yaml`` is the machine's canonical
document; this module reads it, and no module writes it.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.domain.cv import SCHEMA_VERSION, CvFacts, find_duplicate_ids


class CvFactStoreError(Exception):
    """A path-qualified, loud failure. Never a partial load, never a default."""


def _path_qualified(exc: ValidationError) -> str:
    """Render each error as ``sections.2.entries.0.bullets.3.text: <message>``."""
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def _assert_ids_unique(facts: CvFacts) -> None:
    """The load-time gate: an ID appears once, ever (D-63).

    ``CvFacts`` normally rejects duplicates structurally, so this is the explicit
    typed re-check at the trust boundary — a state that reached the store by any
    other route still fails here rather than rendering two different facts under
    one ID.
    """
    duplicates = find_duplicate_ids(facts)
    if duplicates:
        raise CvFactStoreError(f"duplicate fact id: {duplicates[0]}")


def load_facts(path: Path) -> CvFacts:
    """Load and validate ``path`` as a :class:`CvFacts`, or raise loudly.

    Every failure mode is one path-qualified :class:`CvFactStoreError`: a missing
    file, a non-decodable or otherwise unreadable file, invalid YAML, a
    schema-version mismatch, a duplicate fact id, or a removed required field.
    Nothing is ever default-filled or partially loaded.
    """
    path = Path(path)
    resolved = path.resolve()
    if not path.exists():
        # A missing file is loud too — never an empty fact store.
        raise CvFactStoreError(f"no CV fact store at {resolved}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CvFactStoreError(f"{resolved}: invalid YAML: {exc}") from exc
    except (OSError, UnicodeError) as exc:
        # A non-decodable file raises a Unicode decode error; an unreadable one
        # unreadable one (permissions, is-a-directory) raises an OSError that the
        # earlier exists() check cannot see. Both are the operator-visible
        # "unreadable fact store" situation and share the one typed failure.
        raise CvFactStoreError(f"{resolved}: unreadable: {exc}") from exc

    # safe_load ONLY. `yaml.load` with the default loader can construct arbitrary
    # Python objects from document content, so it is never reached here.
    try:
        facts = CvFacts.model_validate(raw)
    except ValidationError as exc:
        raise CvFactStoreError(f"{resolved}: {_path_qualified(exc)}") from exc

    if facts.schema_version != SCHEMA_VERSION:
        raise CvFactStoreError(
            f"{resolved}: schema_version {facts.schema_version!r} != {SCHEMA_VERSION}"
        )

    _assert_ids_unique(facts)
    return facts


__all__ = ["CvFactStoreError", "load_facts"]
