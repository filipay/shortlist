"""WR-03 — the recorded stop-signal parse is structural and fails closed.

The ledger note is written by `classify_response` as `f"... {stop_signal!r}; ..."`.
`repr()` emits SINGLE quotes unless the value contains one, in which case it
switches to DOUBLE quotes — `repr("it's")` is `'"it\\'s"'`. The old prefix
(`"fetch-side: stop signal '"`) therefore missed a single-quote signal, returned
`None`, and silently dropped the stop signal from the badge: the source read as
healthy rather than degraded, a false negative on the exact signal that detects a
block page returning 200 (CONVENTIONS rules 1 and 2).

The literal repro string below is what ingest actually writes for `it's`; it must
now parse, and a note that carries the prefix but no quoted value must NOT read as
"absent".
"""

from __future__ import annotations

from types import SimpleNamespace

from app.db.repositories import source_repo

#: `f"fetch-side: stop signal {stop_signal!r}; recorded and stopped, never retried"`
#: for `stop_signal="it's"` — the double-quoted shape the old parse missed.
SINGLE_QUOTE_SIGNAL_NOTE = 'fetch-side: stop signal "it\'s"; recorded and stopped, never retried'


def test_a_single_quote_signal_is_not_silently_absent() -> None:
    assert source_repo._recorded_stop_signal(SINGLE_QUOTE_SIGNAL_NOTE) == "it's"


def test_the_normal_single_quoted_signal_still_parses() -> None:
    note = "fetch-side: stop signal 'blocked'; recorded and stopped, never retried"

    assert source_repo._recorded_stop_signal(note) == "blocked"


def test_an_unparseable_stop_signal_note_is_not_treated_as_absent() -> None:
    """Fail closed: no quoted value still means "a stop signal was recorded"."""
    note = "fetch-side: stop signal blocked; recorded and stopped, never retried"

    assert source_repo._recorded_stop_signal(note) is not None


def test_a_clean_or_parse_side_note_is_absent() -> None:
    assert source_repo._recorded_stop_signal("parse-side: the request returned no rows") is None
    assert source_repo._recorded_stop_signal("ok: HTTP 200 returned 3 rows") is None


def test_a_single_quote_signal_classifies_fetch_side_not_healthy() -> None:
    """The end-to-end consequence: the badge degrades rather than reading healthy."""
    row = SimpleNamespace(note=SINGLE_QUOTE_SIGNAL_NOTE, status_code=200, ok=True)

    result = source_repo._classify_ledger_row(row)

    assert result.status == "warn"
    assert result.observed == "fetch-side"
