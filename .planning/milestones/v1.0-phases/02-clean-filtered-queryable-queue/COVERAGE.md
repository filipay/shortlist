# API Coverage — Phase 2

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

No external API integration: Phase 2 adds no network adapter and makes no external call — it
consumes only the local SQLite database (FTS5, Alembic migration 0002) and one in-process Python
library (`rapidfuzz`) for Tier-2 dedup. The only external surfaces in the project (JobSpy for
LinkedIn/Indeed, and the opencode server) were fully enumerated in Phase 1's `COVERAGE.md` and are
unchanged by this phase; Adzuna is explicitly deferred to Phase 8 (SRC-11).
`ROADMAP.md` Phase 2 states no LLM call is made — ranking/scoring is Phase 5.

Detector note: the deterministic `api-coverage.cjs` probe returned `detected:true` for this phase's
scope, but the match is a false positive — it fired on the noun `api` in the *label* of the research
document's security table (`| V13 API & Web Service | yes | ...`), not on any integration verb
targeting an external service. Re-reading the phase scope confirms no external API is integrated, so
this reasoned declaration replaces a matrix rather than fabricating capability rows for a service
that does not exist.
