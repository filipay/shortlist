"""The FTS5 safety transform: untrusted text in, a parseable query expression out.

**Why this exists.** FTS5 parses `MATCH`'s right-hand side as a *query expression*,
not as a literal string, so ordinary human input is a syntax error waiting to happen.
Verified by execution against the real `listing_fts` table (RESEARCH §Q3), every one
of these raised `sqlite3.OperationalError` when passed through raw:

===================  =====================================
input                error
===================  =====================================
a lone hyphen        ``fts5: syntax error near ""``
a trailing ``AND``   ``fts5: syntax error near ""``
``"unbalanced``      ``unterminated string``
the bare word ``OR``  ``fts5: syntax error near "OR"``
``*``                ``unknown special query:``
``NEAR(``            ``fts5: syntax error near ""``
a hyphenated word    ``no such column: up`` (``runner-up``)
an apostrophe form   ``fts5: syntax error near "'"`` (``it's``)
===================  =====================================

Quoting **each token** is the only correct escape: it turns every token into an
FTS5 *string* (a literal term), so the parser has no operators left to misread. A
single token is quoted like any other — ``"-"`` matches a literal hyphen.

Pure by contract: standard library only, no I/O, no settings, no stemming (the
table's own ``porter unicode61`` tokenizer does the stemming, and a second stemmer
here would silently change what matches).
"""

from __future__ import annotations

import re

#: FTS5's own escape for a literal double quote inside a quoted string is to double
#: it. This module therefore never strips or rewrites the user's characters — it
#: only wraps them.
_QUOTE = '"'

_TOKEN_SPLIT = re.compile(r"\s+")


def _quote_token(token: str) -> str:
    """One token as an FTS5 string: wrapped, with internal quotes doubled."""
    return _QUOTE + token.replace(_QUOTE, _QUOTE * 2) + _QUOTE


def build_match_expression(raw: str | None, *, prefix_last: bool = True) -> str | None:
    """A safe FTS5 `MATCH` expression for `raw`, or `None` when there is no query.

    `None` is the D-42 "no query present" branch: the caller must then skip the
    `listing_fts` join entirely and keep the deterministic recent-first order. An
    empty or whitespace-only query takes the same branch — the database is never
    handed `MATCH ''`.

    Tokens are whitespace-separated, each is quoted, they are joined with ` AND `,
    and (by default) the last one gets a trailing `*` so the queue matches as the
    user is still typing. Total: never raises, for any `str` or `None`.

    The prefix `*` applies to the last token only, which is what makes a
    left-to-right query box feel responsive without turning every token into a
    prefix scan.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):  # defensive at the boundary; the route always passes str
        raw = str(raw)

    tokens = [token for token in _TOKEN_SPLIT.split(raw.strip()) if token]
    if not tokens:
        return None

    quoted = [_quote_token(token) for token in tokens]
    if prefix_last:
        quoted[-1] = f"{quoted[-1]}*"
    return " AND ".join(quoted)


__all__ = ["build_match_expression"]
