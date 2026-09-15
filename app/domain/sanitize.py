"""Pure sanitisation: the Phase-1 scope only (PITFALLS Pitfall 7).

Phase 1 ships the *named stage* with four behaviours — email/phone stripping,
HTML-to-text reduction with whitespace collapsing, description truncation, and an
`instruction_like` flag. The pattern catalogue for the flag is deliberately a
Phase-2 task; over-reaching here is as wrong as under-reaching.

PII is **dropped, never hashed** (a hashed phone number is still personal data
that serves no product purpose), and the removed value is never returned or
logged — only a count.

**Truncation unit (the SRC-08 contract).** `max_chars` counts **Python `str`
characters** (Unicode code points) — not bytes and not grapheme clusters. A
multi-byte description of `max_chars + 1` code points therefore yields exactly
`max_chars` code points, and its UTF-8 encoding is legitimately longer than
`max_chars` bytes. Slicing bytes would split a character mid-sequence and raise;
segmenting grapheme clusters would require a dependency this phase deliberately
does not take. The contract is stated in `sanitize_text`'s docstring and pinned
by a multi-byte test (`tests/domain/test_sanitize_edge.py`).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
BLOCK_TAG_RE = re.compile(r"</?(?:p|div|br|li|tr|h[1-6]|section|article)\b[^>]*>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?<![\w])(?:\+\d[\d\s().\-]{6,}\d|\b0\d[\d\s().\-]{6,}\d)(?![\w])"
)
SPACE_RE = re.compile(r"[ \t\u00a0\r\f\v]+")
NEWLINE_RE = re.compile(r"\n\s*\n\s*")

#: Imperative / system-style markers that suggest injected instructions.
#: Phase 1 only *flags* them; the full rule catalogue is Phase 2.
INSTRUCTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "ignore the above",
    "disregard previous",
    "disregard the above",
    "system prompt",
    "new instructions",
    "you are now",
    "as an ai language model",
    "do not tell the user",
)


@dataclass(frozen=True)
class SanitizeReport:
    """What was removed/changed. Counts only — never the removed value."""

    emails_removed: int = 0
    phones_removed: int = 0
    html_removed: bool = False
    truncated: bool = False
    instruction_like: bool = False

    def merge(self, other: SanitizeReport) -> SanitizeReport:
        return SanitizeReport(
            emails_removed=self.emails_removed + other.emails_removed,
            phones_removed=self.phones_removed + other.phones_removed,
            html_removed=self.html_removed or other.html_removed,
            truncated=self.truncated or other.truncated,
            instruction_like=self.instruction_like or other.instruction_like,
        )


@dataclass(frozen=True)
class SanitisedText:
    """One sanitised field: the cleaned text plus the counts that describe it.

    Deliberately *only* counts. There is no field on this type able to carry the
    removed value, so a caller cannot accidentally persist or log the PII the
    sanitiser just dropped.
    """

    text: str
    report: SanitizeReport


#: The plan's alternate spelling, retained so callers written against plan 01-03
#: keep importing without a churn-only rename.
SanitizeResult = SanitisedText


def strip_html(value: str) -> tuple[str, bool]:
    """Reduce HTML to text. Script/style *content* is removed, not just tags."""
    if not value:
        return "", False
    original = value
    text = SCRIPT_STYLE_RE.sub(" ", value)
    text = BLOCK_TAG_RE.sub("\n", text)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return text, text != original


def strip_pii(value: str) -> tuple[str, int, int]:
    """Drop recruiter emails and phone numbers. Returns (text, emails, phones)."""
    if not value:
        return "", 0, 0
    emails = EMAIL_RE.findall(value)
    text = EMAIL_RE.sub(" ", value)
    phones = PHONE_RE.findall(text)
    text = PHONE_RE.sub(" ", text)
    return text, len(emails), len(phones)


def collapse_whitespace(value: str) -> str:
    text = SPACE_RE.sub(" ", value)
    text = NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def looks_like_instructions(value: str) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    return any(marker in lowered for marker in INSTRUCTION_MARKERS)


def sanitize_text(value: str | None, *, max_chars: int) -> SanitisedText:
    """The full Phase-1 treatment for one untrusted field.

    `max_chars` is supplied by the caller (the ingest stage reads it from
    settings) so this module stays free of configuration and I/O.

    `max_chars` counts **Python characters (code points)**, not bytes and not
    grapheme clusters: truncation is a plain ``text[:max_chars]`` slice, so the
    result is *exactly* `max_chars` characters whenever the input is longer. The
    function is total (a `None` or empty input yields `""`) and deterministic —
    there is no dict iteration order, locale or timestamp anywhere in the path,
    so sanitising the same input twice returns equal output.
    """
    if not value:
        return SanitisedText("", SanitizeReport())

    text, html_removed = strip_html(value)
    text, emails, phones = strip_pii(text)
    text = collapse_whitespace(text)

    truncated = len(text) > max_chars
    if truncated:
        # Exactly `max_chars` characters. Never `.rstrip()` (which would return
        # fewer than the documented limit) and never a byte slice (which would
        # split a multi-byte character and raise).
        text = text[:max_chars]

    return SanitisedText(
        text,
        SanitizeReport(
            emails_removed=emails,
            phones_removed=phones,
            html_removed=html_removed,
            truncated=truncated,
            instruction_like=looks_like_instructions(text),
        ),
    )


def sanitize_short_field(value: str | None, *, max_chars: int) -> SanitisedText:
    """Sanitise a short field (title, company, location) without over-truncating."""
    return sanitize_text(value, max_chars=max_chars)


__all__ = [
    "INSTRUCTION_MARKERS",
    "SanitizeReport",
    "SanitizeResult",
    "SanitisedText",
    "collapse_whitespace",
    "looks_like_instructions",
    "sanitize_short_field",
    "sanitize_text",
    "strip_html",
    "strip_pii",
]
