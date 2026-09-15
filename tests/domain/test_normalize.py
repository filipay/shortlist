"""SRC-03 — pure normalisation: canonical URLs, stable hashes, deterministic output."""

from __future__ import annotations

from app.domain.listing import (
    annualise_salary,
    canonical_url,
    content_hash,
    normalise_company_name,
)
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing


def _raw(**overrides: object) -> RawListing:
    base: dict[str, object] = {
        "source": "linkedin",
        "source_listing_id": "abc-1",
        "source_url": "https://ie.linkedin.com/jobs/view/1",
        "direct_url": None,
        "title": "Senior Python Engineer",
        "company_name": "Acme Ltd",
        "location_raw": "Dublin, Ireland",
        "description": "Build the thing.",
    }
    base.update(overrides)
    return RawListing(**base)  # type: ignore[arg-type]


# --- canonical_url ------------------------------------------------------------
def test_canonical_url_strips_tracking_params_and_sorts_the_rest() -> None:
    raw = "https://IE.LinkedIn.com/jobs/view/1?utm_source=x&trk=abc&b=2&a=1#fragment"

    assert canonical_url(raw) == "https://ie.linkedin.com/jobs/view/1?a=1&b=2"


def test_canonical_url_prefers_the_direct_url_when_present() -> None:
    board = "https://ie.linkedin.com/jobs/view/1?trk=abc"
    direct = "https://acme.example.com/careers/1?utm_campaign=y"

    assert canonical_url(board, direct) == "https://acme.example.com/careers/1"


def test_canonical_url_drops_the_default_port_and_trailing_slash() -> None:
    assert canonical_url("https://example.com:443/jobs/1/") == "https://example.com/jobs/1"


def test_canonical_url_is_stable_across_repeat_calls() -> None:
    raw = "https://example.com/jobs/1?b=2&a=1&utm_medium=email"

    assert canonical_url(raw) == canonical_url(raw)


# --- content_hash -------------------------------------------------------------
def test_content_hash_is_stable_across_repeat_calls() -> None:
    kwargs = {
        "title": "Senior Python Engineer",
        "company_name": "Acme",
        "location_raw": "Dublin, Ireland",
        "description": "Build the thing.",
    }

    assert content_hash(**kwargs) == content_hash(**kwargs)


def test_content_hash_changes_when_any_input_changes() -> None:
    base = {
        "title": "Senior Python Engineer",
        "company_name": "Acme",
        "location_raw": "Dublin, Ireland",
        "description": "Build the thing.",
    }
    baseline = content_hash(**base)

    for key, value in (
        ("title", "Staff Python Engineer"),
        ("company_name", "Globex"),
        ("location_raw", "Cork, Ireland"),
        ("description", "Run the thing."),
    ):
        changed = dict(base)
        changed[key] = value
        assert content_hash(**changed) != baseline, f"{key} did not change the hash"


def test_content_hash_ignores_volatile_inputs_by_construction() -> None:
    # The signature has no salary/timestamp parameters at all: a repost-detection
    # hash that moved with `last_seen_at` would report a change every run.
    import inspect

    parameters = set(inspect.signature(content_hash).parameters)
    assert parameters == {"title", "company_name", "location_raw", "description"}


# --- normalise_listing --------------------------------------------------------
def test_empty_or_none_description_is_deterministic() -> None:
    first = normalise_listing(_raw(description=None))
    second = normalise_listing(_raw(description=None))

    assert first.description is None
    assert first.content_hash == second.content_hash


def test_normalising_the_same_record_twice_is_byte_identical() -> None:
    raw = _raw()

    first = normalise_listing(raw)
    second = normalise_listing(raw)

    assert first.canonical_url == second.canonical_url
    assert first.content_hash == second.content_hash
    assert first.raw_hash == second.raw_hash


def test_different_urls_with_equal_company_title_and_location_stay_distinct() -> None:
    a = normalise_listing(_raw(source_url="https://example.com/a"))
    b = normalise_listing(_raw(source_url="https://example.com/b"))

    # Tier-1 is exact-key only: different canonical URLs are different listings.
    assert a.canonical_url != b.canonical_url
    # ... but the content signal correctly says they are the same content.
    assert a.content_hash == b.content_hash


def test_normalise_sets_the_dedup_keys_and_apply_url() -> None:
    normalised = normalise_listing(_raw(direct_url="https://acme.example.com/1"))

    assert normalised.source_listing_id == "abc-1"
    assert normalised.canonical_source_url == normalised.canonical_url
    assert normalised.apply_url == "https://acme.example.com/1"
    assert normalised.company_norm == "acme"
    assert normalised.blocking_key is not None


# --- helpers ------------------------------------------------------------------
def test_normalise_company_name_drops_legal_suffixes_and_punctuation() -> None:
    assert normalise_company_name("Acme Ltd.") == "acme"
    assert normalise_company_name("Globex, Inc") == "globex"
    assert normalise_company_name(None) is None


def test_annualise_salary_converts_monthly_to_annual() -> None:
    assert annualise_salary(4000, 5000, "month", "EUR") == (48000, 60000, "year", "EUR")


def test_annualise_salary_passes_through_an_unknown_interval() -> None:
    assert annualise_salary(10, 20, "fortnight", "EUR") == (10, 20, "fortnight", "EUR")
