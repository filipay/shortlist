"""Pure listing-field derivation: the functions that carry the dedup guarantee.

No I/O, no settings — every function is deterministic and unit-testable. The
normalise stage (`app/pipeline/stages.py`) composes these into a
`NormalisedListing`.

Why purity matters here: both Tier-1 dedup keys (`source_listing_id` and the
canonical URL) depend on these, and "normalising the same record twice gives
byte-identical values" is a queue-integrity property, not a nicety.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# --- text normalisation -------------------------------------------------------

WHITESPACE_RE = re.compile(r"\s+")
PUNCTUATION_RE = re.compile(r"[^\w\s]")

#: Company legal suffixes are not part of the dedup identity ("Acme Ltd" == "Acme").
LEGAL_SUFFIXES = frozenset(
    {
        "limited",
        "ltd",
        "inc",
        "incorporated",
        "llc",
        "llp",
        "gmbh",
        "ag",
        "bv",
        "nv",
        "plc",
        "corp",
        "corporation",
        "co",
        "sa",
        "srl",
    }
)


def collapse_whitespace(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def normalise_text(value: str | None) -> str | None:
    """Casefolded, whitespace-collapsed value; `None` for empty input."""
    if value is None:
        return None
    collapsed = collapse_whitespace(value).casefold()
    return collapsed or None


def normalise_title(title: str | None) -> str:
    """Titles always produce a string (the DB column is non-null in practice)."""
    return normalise_text(title) or ""


def normalise_location(location: str | None) -> str | None:
    return normalise_text(location)


def normalise_company_name(name: str | None) -> str | None:
    """The `companies.name_norm` anchor: casefold, drop punctuation and legal suffixes."""
    if name is None:
        return None
    text = PUNCTUATION_RE.sub(" ", collapse_whitespace(name).casefold())
    tokens = [token for token in text.split() if token and token not in LEGAL_SUFFIXES]
    collapsed = " ".join(tokens).strip()
    return collapsed or None


def blocking_key(company_norm: str | None, title_norm: str | None) -> str | None:
    """An indexed equality key so Tier-2 candidate lookup is not a scan (§9.2)."""
    if not company_norm and not title_norm:
        return None
    title_tokens = sorted(set((title_norm or "").split()))
    return f"{company_norm or ''}|{' '.join(title_tokens)}"[:255]


# --- URL canonicalisation -----------------------------------------------------

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = frozenset(
    {
        "gh_src",
        "lever-source",
        "src",
        "ref",
        "trk",
        "trkemail",
        "trackingid",
        "originalreferer",
        "position",
        "pagenum",
        "ebcc",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
)
DEFAULT_PORTS = {"http": 80, "https": 443}


def _is_tracking(key: str) -> bool:
    lowered = key.casefold()
    return lowered in TRACKING_KEYS or lowered.startswith(TRACKING_PREFIXES)


def canonical_url(raw: str, direct: str | None = None) -> str:
    """Canonicalise a listing URL.

    Lowercase scheme+host, drop the default port, strip tracking parameters, sort
    the rest, drop the fragment, normalise a trailing slash. `direct` (the
    employer's own listing) is preferred when present — it is the Tier-2a
    cross-source signal.

    Every miss here is a duplicate that Tier-1 fails to catch.
    """
    candidate = (direct or raw or "").strip()
    if not candidate:
        return ""

    parts = urlsplit(candidate)
    if not parts.scheme and not parts.netloc:
        # Not a URL we can normalise — return it trimmed rather than mangling it.
        return candidate

    scheme = (parts.scheme or "https").casefold()
    host = (parts.hostname or "").casefold()
    if not host:
        return candidate

    try:
        port = parts.port
    except ValueError:
        port = None

    netloc = host
    if port is not None and DEFAULT_PORTS.get(scheme) != port:
        netloc = f"{host}:{port}"

    query_pairs = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking(key)
    )

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, urlencode(query_pairs), ""))


# --- digests ------------------------------------------------------------------


def _digest(*parts: str | None) -> str:
    payload = "\x1f".join(collapse_whitespace(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def content_hash(
    *,
    title: str | None,
    company_name: str | None,
    location_raw: str | None,
    description: str | None,
) -> str:
    """Stable hash over the SANITISED fields only.

    Used for repost/update detection and as a Tier-2c duplicate signal. It must
    not include volatile fields (salary, `last_seen_at`) or every run would look
    like a change.
    """
    return _digest(title, company_name, location_raw, description)


def description_hash(description: str | None) -> str | None:
    if not description:
        return None
    return hashlib.sha256(description.encode("utf-8")).hexdigest()


def raw_fingerprint(
    *,
    source: str | None,
    source_listing_id: str | None,
    source_url: str | None,
    title: str | None,
    company_name: str | None,
    location_raw: str | None,
    description: str | None,
) -> str:
    """Hash of the identifying raw fields — detects silent field changes (S5)."""
    return _digest(
        source, source_listing_id, source_url, title, company_name, location_raw, description
    )


# --- salary -------------------------------------------------------------------

ANNUAL_MULTIPLIERS = {
    "year": 1,
    "yearly": 1,
    "annual": 1,
    "annually": 1,
    "month": 12,
    "monthly": 12,
    "week": 52,
    "weekly": 52,
    "day": 260,
    "daily": 260,
    "hour": 2080,
    "hourly": 2080,
}


def annualise_salary(
    minimum: float | None,
    maximum: float | None,
    interval: str | None,
    currency: str | None,
) -> tuple[float | None, float | None, str | None, str | None]:
    """Convert a salary range to an annual figure where the interval is known.

    Note for Ireland: JobSpy's description-derived salary extraction is USA-only
    and `$`-anchored, so an Irish search has a *structurally low* salary fill-rate.
    An unknown interval is passed through unchanged rather than guessed.
    """
    if minimum is None and maximum is None:
        return minimum, maximum, interval, currency

    factor = ANNUAL_MULTIPLIERS.get((interval or "").strip().casefold())
    if factor is None:
        return minimum, maximum, interval, currency

    return (
        minimum * factor if minimum is not None else None,
        maximum * factor if maximum is not None else None,
        "year",
        currency,
    )


# --- required experience ------------------------------------------------------
#
# A listing's own description sometimes names a years floor the ranker has no
# explicit sight of. These helpers surface it deterministically so the seniority
# factor can weigh it and the rationale can name a shortfall honestly. They are a
# SOFT signal: absence returns `None` (never "0 required"), a preference-qualified
# figure is not a requirement, and nothing here filters or hides a listing.

#: The leading captured group is the required floor; the optional tail is a plus
#: ("+" / "plus") and/or a range (an en/em dash or "to" followed by a second number).
_REQUIRED_EXPERIENCE_RE = re.compile(
    r"\b(\d{1,2}(?:\.\d+)?)\s*(?:\+|\bplus\b)?\s*"
    r"(?:(?:[-–—]|\bto\b)\s*\d{1,2}(?:\.\d+)?\s*)?"
    r"(?:years?|yrs?)\b",
    re.IGNORECASE,
)

#: A clause is the span around a match, split on punctuation and the coordinating
#: words — a qualifier elsewhere in the sentence must not silence a clean clause.
_CLAUSE_SPLIT_RE = re.compile(r"[,;.!?\n]|\band\b|\bbut\b", re.IGNORECASE)

#: The designated not-required class. A figure carrying any of these is a
#: preference, not a requirement (the single biggest error class in extraction).
_REQUIRED_EXPERIENCE_QUALIFIERS = (
    "preferred",
    "ideally",
    "desirable",
    "nice to have",
    "advantage",
    "beneficial",
    "an asset",
    "bonus",
    "a plus",
)


def _clause_spans(text: str) -> list[tuple[int, int, str]]:
    """`(start, end, clause)` triples for `text`, in order."""
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in _CLAUSE_SPLIT_RE.finditer(text):
        spans.append((start, match.start(), text[start : match.start()]))
        start = match.end()
    spans.append((start, len(text), text[start:]))
    return spans


def _required_experience_match(description: str | None) -> re.Match[str] | None:
    """The first usable match, or `None`.

    A match with a non-positive floor ("0-2 years") is skipped as no signal, and a
    match whose clause carries a preference qualifier is skipped. Both public
    helpers derive from this one scan so they can never drift.
    """
    if not description:
        return None
    clause_spans = _clause_spans(description)
    for match in _REQUIRED_EXPERIENCE_RE.finditer(description):
        if int(float(match.group(1))) <= 0:
            continue
        for clause_start, clause_end, clause in clause_spans:
            if clause_start <= match.start() < clause_end:
                if any(q in clause.casefold() for q in _REQUIRED_EXPERIENCE_QUALIFIERS):
                    break
                return match
    return None


def required_experience_years(description: str | None) -> int | None:
    """The stated years floor, or `None` when there is no usable signal.

    The leading number of a range is the floor ("3-5 years" -> 3). `None` means the
    description states no requirement — it is NEVER zero required and never a penalty.
    """
    match = _required_experience_match(description)
    return None if match is None else int(float(match.group(1)))


def required_experience_fragment(description: str | None) -> str | None:
    """The exact matched substring, or `None`.

    Quoting the listing's own words keeps a misread visible rather than silent.
    """
    match = _required_experience_match(description)
    return None if match is None else match.group(0)


__all__ = [
    "ANNUAL_MULTIPLIERS",
    "LEGAL_SUFFIXES",
    "TRACKING_KEYS",
    "TRACKING_PREFIXES",
    "annualise_salary",
    "blocking_key",
    "canonical_url",
    "collapse_whitespace",
    "content_hash",
    "description_hash",
    "normalise_company_name",
    "normalise_location",
    "normalise_text",
    "normalise_title",
    "raw_fingerprint",
    "required_experience_fragment",
    "required_experience_years",
]
