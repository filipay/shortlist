"""Default-lane isolation for the surface-detection cache (07.1-01).

`app.llm.detection._CACHE` is process-local and lives for the whole process, so a
test that caches a V1/V2 verdict for a `base_url` would leak it into the next test
and make a recorder's probe count non-deterministic. Clearing it per test keeps
each test's recorder authoritative.
"""

from __future__ import annotations

import pytest

from app.llm import detection


@pytest.fixture(autouse=True)
def _clear_detection_cache() -> None:
    detection.clear_cache()
    yield
    detection.clear_cache()
