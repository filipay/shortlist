"""Liveness-probe orchestration (SRC-07 / D-03(c)).

`probe()` itself lives on the adapter, where the board knowledge already is (the
known-stable URL, the expected structural marker). This package holds only the
board-agnostic part: resolve the enabled sources, call each adapter's probe, cache
the result for a TTL and never raise.

The two instruments are deliberately kept apart (RESEARCH §Scraper-Survival Probe
Design): this is *liveness* ("is the board reachable right now?"), while the
survival measurement S1-S6 is plan 01-07's job.
"""

from app.probe.probe import clear_cache, probe_all, probe_source

__all__ = ["clear_cache", "probe_all", "probe_source"]
