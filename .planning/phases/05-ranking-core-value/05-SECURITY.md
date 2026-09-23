---
phase: "05"
slug: "ranking-core-value"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
security_block_on: high
created: "2026-09-22"
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS L1** (grep-level presence). The register was authored at plan time in the PLAN files of all ten plans (the round-2 rows were appended by the 2026-09-23 gap-closure re-audit), so per the secure-phase short-circuit (`threats_open: 0`, `register_authored_at_plan_time: true`, `asvs_level: 1`) L1 presence verification is sufficient. `security_block_on = high`.

**Scope audited:** LLM ranking pipeline (`app/pipeline/rank.py`), detached ranking lifecycle (`start_ranking_task`), spend caps (`app/config.py`, `app/db/repositories/llm_call_repo.py`), ranking-weights write path (`app/api/settings.py`, `app/db/repositories/ranking_config_repo.py`), new `GET /listings/{id}` route (`app/api/listings.py`, registered `app/main.py:63`), the new HTML/Jinja templates (`listing_detail.html`, `queue.html`, `queue_list.html`, `settings.html`, `_listing_row.html`), the queue ranking strip (`app/web/routes.py` `_ranking_strip`, `app/db/repositories/run_repo.py` `RunSummary.candidate_count` / `_optional_int`, `queue.html`), and the CV fact-store reader (`app/cv/factstore.py` `load_facts`).

**Register hygiene note:** `T-05-SC` is declared once in each of the ten PLAN files with a per-plan scope; there are 47 unique numbered threats (`T-05-01`…`T-05-47`) plus the ten `T-05-SC` occurrences — 57 registered rows, 48 unique threats. The ten `T-05-SC` rows are presented as one row below.

**Gap-closure re-audit (2026-09-22):** the register was first written against plans 05-01…05-04. Plans 05-05 and 05-06 (both `gap_closure: true`) subsequently landed and declared eight further rows (`T-05-22`…`T-05-29`) plus a per-plan `T-05-SC`. Those rows are appended below; the pre-existing rows are preserved unchanged and were not re-litigated.

**Round-2 gap-closure re-audit (2026-09-23):** the round-2 gap-closure plans 05-07…05-10 (all `gap_closure: true`) subsequently landed and declared eighteen further rows (`T-05-30`…`T-05-47`) plus a per-plan `T-05-SC`. Those are appended below; the pre-existing rows are preserved unchanged.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| listing text → LLM prompt | Untrusted job-board text (title, company, description) crosses into the model's user turn | Untrusted listing text |
| CV facts → LLM prompt | The user's private CV content crosses into the model's user turn | Private CV content (ids + prose) |
| model response → database | Model-produced sub-scores, rationale and evidence ids cross into `scores` rows | Model output, untrusted-shaped |
| browser → queue / detail render | Untrusted listing text and model prose cross back into HTML | Untrusted text → HTML |
| settings → cap decision | Operator-supplied ceilings gate every outbound model call | Integer ceilings |
| `llm_calls` ledger → cap decision | Persisted call counts gate the next call | Call counts |
| listing content → call accounting | Untrusted listing text must not influence whether/how many calls are made | (control boundary) |
| process lifetime → in-flight counter | A module-level counter is the only in-process spend state | Counter integer |
| browser → `/listings/{id}` | An untrusted path parameter selects a row | Integer path param |
| browser → `/settings/weights` | Untrusted form values cross into the persisted weights document | Form floats |
| browser → queue query string | Untrusted `sort` and `min_score` values cross into the read model | Query params |
| persisted weights → queue order | Operator configuration determines the displayed ranking | Weights document |
| persisted `runs.reason_counts_json` → HTML strip | A database JSON column (written by the pipeline, editable by hand or an older build) crosses into rendered markup | Persisted JSON → HTML |
| persisted `runs.ranked_count` → HTML strip | A nullable integer column crosses into the ratio the user reads | Integer → HTML |
| operator filesystem → `load_facts` | A `cv.yaml` outside the repo is parsed; its bytes/encoding/readability are not under the application's control | File bytes → parsed fact store |
| `load_facts` failure → detached ranking task | A load failure crosses into the fire-and-forget task, where an unhandled exception is never retrieved | Exception → task lifecycle |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Tampering | `build_ranking_parts` / `complete_structured` call | high | mitigate | `RANK_SYSTEM_PROMPT` is a frozen plain literal with no f-string/`%`/format (`app/pipeline/rank.py:83-107`); `to_message_body(system=...)` passes it verbatim and exposes no argument that can alter it (`app/llm/builders.py:55-108`); listing + CV text travel only in `parts` via `build_ranking_parts` (`rank.py:178-188`); asserted `tests/pipeline/test_rank_stage.py:139-149` and one-listing-per-prompt `:151-168` | closed |
| T-05-02 | Elevation of Privilege | opencode session | high | mitigate | `tools=()` on every ranking call (`rank.py:234`) → `tool_grant=None` emits no message-level `tools` key (`app/llm/opencode_server.py:472`); enforced deny is the session `DEFAULT_DENY_RULES` catch-all (`opencode_server.py:117,376`); `compose.yml` publishes only `8000:8000` and declares no opencode service / 4096 port (`compose.yml:3-10`); `tools == ()` asserted `tests/pipeline/test_rank_stage.py:166` | closed |
| T-05-03 | Repudiation | `llm_calls` audit trail | medium | mitigate | Exactly one audit row per call, success or failure, written before the early return (`rank.py:238-247`); `record_llm_call` maps `provider/model/agent/server_version/latency/attempts/error` from the result (`app/db/repositories/llm_call_repo.py:108-141`); vocabulary validated pre-SQL (`:103-106`) | closed |
| T-05-04 | Tampering | `_listing_row.html` score badge | medium | mitigate | Zero `\|safe` in any template (grep, whole `app/web/templates/`); badge renders a rounded float via `"%.2f"\|format` and a tier string (`_listing_row.html:48-50`); tier vocabulary validated against `CONFIDENCE_TIERS` before SQL (`app/db/repositories/score_repo.py`) and constrained by CHECK `('high','medium','low')` (`app/db/models.py:380`) | closed |
| T-05-05 | Information Disclosure | CV content | medium | accept | No new outbound host is introduced: the only network path is the existing external opencode server (`compose.yml:3-19`); CV content never leaves the container in v1 (PROJECT.md privacy constraint). Does not resurface. | closed |
| T-05-06 | Denial of Service | `_salvage` / schema validation | low | accept | A model response failing validation returns `None` and writes no score row (`rank.py:249-250`); the per-listing loop isolates each failure and continues (`rank.py:447-462`). Accepted at personal scale. | closed |
| T-05-SC | Tampering (supply chain) | npm/pip/cargo installs (05-01…05-10) | high | mitigate | No package installed by any part of this phase: `pyproject.toml`/`uv.lock`/`requirements` are unchanged across every phase-5 commit, including the 05-05…05-10 gap-closure commits (they touch only `app/`, `tests/`, `static/` and `.planning/`); Alembic head stays `0004` (no `0005` migration exists); the one build-output edit (05-10 hand-added the `.cv-status` rule to the committed vendored `static/vendor/app.css`) installs nothing and is guarded by `tests/test_stylesheet_coverage.py`; `python-multipart` stays absent; vendored-assets guard `tests/test_no_cdn.py` | closed |
| T-05-07 | Denial of Service | `_reserve` / ranking loop | high | mitigate | `_reserve` runs BEFORE `rank_listing` under `asyncio.Lock` (`rank.py:409,324-335`); both ceilings checked (`_cap_hit`, `rank.py:310-321`); refusal is graceful and issues no request (`rank.py:409-434`); asserted `tests/pipeline/test_rank_caps.py:57-86` (second call refused before issue) and rolling-24h `:112-137` | closed |
| T-05-08 | Denial of Service | `rank_calls_since` aggregate | medium | accept | Full scan on an unindexed column accepted deliberately and recorded in the function docstring (`app/db/repositories/llm_call_repo.py:229-232`); no index migration added. Does not resurface. | closed |
| T-05-09 | Tampering | in-flight counter | medium | mitigate | `_in_flight` mutated only under `_reserve_lock` (`rank.py:331,341`); released in a `finally` (`rank.py:461-462`); `max(0, ...)` floor (`rank.py:342`); `ponytail:` comment names the single-worker assumption + advisory-lock upgrade path (`rank.py:303-305`) | closed |
| T-05-10 | Repudiation | refusal audit | medium | mitigate | Each refusal writes one `llm_calls` row `purpose="rank"`, `status="error"`, cap name encoded in `error` after `BUDGET_EXCEEDED_MARKER` (`rank.py:417-424`; marker `llm_call_repo.py:49`); read back by `rank_cap_reason_for_run` (`:244-268`); asserted `tests/pipeline/test_rank_caps.py:72-86` | closed |
| T-05-11 | Elevation of Privilege | `_RANKING_TASK` single-flight guard | low | mitigate | Module-level `_RANKING_TASK` start-or-skip, never queues (`rank.py:504,523-534`); strong-reference set prevents GC (`:496,533-534`) | closed |
| T-05-12 | Tampering | `listing_detail.html` title/rationale render | high | mitigate | Jinja autoescape only, no `\|safe` anywhere (`listing_detail.html`, verified by grep); dedicated test seeds `<script>x</script>` into **both** title and rationale and asserts the raw tag is absent and the escaped form renders (`tests/api/test_listing_detail.py:214-224`) | closed |
| T-05-13 | Tampering | `listing_id` path parameter | medium | mitigate | Typed `listing_id: int` by FastAPI (`app/api/listings.py:64`), so non-numeric never reaches the query; repository uses bound parameters; unknown id returns the 404 fragment (`:54-59`); asserted `tests/api/test_listing_detail.py:228-233` | closed |
| T-05-14 | Information Disclosure | CV fact ids on detail page | low | accept | Fact ids are internal stable identifiers rendered as text for the user's own review (`listing_detail.html:82`); the page is behind the `current_user` seam (`listings.py:66`) and v1 is single-user local. Does not resurface. | closed |
| T-05-15 | Spoofing | external anchors | medium | mitigate | Every external anchor carries `rel="noopener noreferrer"` and renders only on a truthy URL (`listing_detail.html:26`; `_listing_row.html:37,55`); `_http_url` http(s)-only scheme gate (`queue_repo.py:568-580`) still applies because the route reuses `read_row` (`:625-626,714`) | closed |
| T-05-16 | Repudiation | save/hide actions on detail page | low | mitigate | Detail page reuses the exact two-form event block, posting the same `save`/`unsave`/`hide`/`unhide` event types to the same append-only `/listings/{id}/events` endpoint (`listing_detail.html:89-118`; `_listing_row.html:65-92`) | closed |
| T-05-17 | Tampering | `POST /settings/weights` parsing | high | mitigate | Every field validated at the storage boundary (`app/api/settings.py:181-214`): non-numeric/non-finite/negative rejected with inline error and nothing written; repository re-validates every key ∈ `rubric.FACTORS` and every value a finite float `>= 0.0` before SQL (`app/db/repositories/ranking_config_repo.py:79-95`); upsert is parameterised (`:98-108`); asserted `tests/api/test_ranking_weights.py:196` | closed |
| T-05-18 | Denial of Service | all-zero weight set | medium | mitigate | An all-zero submission is refused because a zero denominator makes every total `None` (`settings.py:212-213`); asserted `tests/api/test_ranking_weights.py:213` | closed |
| T-05-19 | Tampering | `min_score` query parameter | medium | mitigate | `_float_or_none` parses tolerantly with junk degrading to `None` (`app/web/routes.py:109-116,140`); the value is compared in Python in `read_queue`, never interpolated into SQL, so a junk value cannot produce a 500. (Code-review WR-03 notes `nan`/`inf` are not finiteness-gated — a robustness gap, not the declared tampering vector; medium severity, below the `high` block threshold.) | closed |
| T-05-20 | Denial of Service | Python-side score sort scan | medium | accept | The score path scans at most `SCORE_SORT_SCAN_LIMIT = 5000` rows before sorting in Python (`app/db/repositories/queue_repo.py:111,444,452`), accepted at personal scale with the materialised-total upgrade path named in the `ponytail:` comment (`:28,108-110`); `?sort=recent` remains selectable. Does not resurface. | closed |
| T-05-21 | Repudiation | weights audit | low | mitigate | `ranking_config.updated_at` records when the document last changed (`ranking_config_repo.py:100-104`); every `scores` row keeps `weights_json` as the audit snapshot of the weights in force at scoring time (`app/db/repositories/score_repo.py:223`) | closed |
| T-05-22 | Repudiation | `_ranking_strip` → `queue.html` `#ranking-strip` | medium | mitigate | The denominator is the run's own persisted candidate population, not the request: `_ranking_strip(session, latest_run)` has no `page` parameter and sources `candidates` from `latest_run.candidate_count` (`app/web/routes.py:276-307`); `_summary` reads it from the run's own `reason_counts_json['survivors']` (`app/db/repositories/run_repo.py:243`); the template prints the ratio only when that value is not none (`queue.html:140`). No user-controlled predicate influences the strip (plan 05-05) | closed |
| T-05-23 | Tampering | `reason_counts_json['survivors']` parse | low | mitigate | `_optional_int` returns `None` for an absent or non-numeric value and never fabricates a `0` denominator (`app/db/repositories/run_repo.py:73-86`); the value is rendered through the autoescaped Jinja environment (zero `\|safe` anywhere in `app/web/templates/`) and is never interpolated into SQL (plan 05-05) | closed |
| T-05-24 | Denial of Service | queue page render path | low | mitigate | `_ranking_strip` keeps its `try/except Exception` guard, `log.warning("queue.ranking_strip_failed", ...)` path and empty-mapping return (`app/web/routes.py:298-310`), so an unreadable or half-written run row yields a page without the strip rather than a 500 (plan 05-05) | closed |
| T-05-25 | Information Disclosure | strip contents | low | accept | The strip renders two integers and a cap-name string only — no listing, CV or personal content. Accepted: there is nothing sensitive in the surface. See AR-05-06 (plan 05-05) | closed |
| T-05-26 | Denial of Service | `app/cv/factstore.py` `load_facts` read | medium | mitigate | A non-decodable or unreadable file is caught as `except (OSError, UnicodeError)` and re-raised as a path-qualified `CvFactStoreError` (`app/cv/factstore.py:68-73`); `run_ranking`'s existing `except (CvFactStoreError, OSError)` guard catches it and returns before the backend or a session is touched (`app/pipeline/rank.py:377-387`), so no exception escapes the fire-and-forget task (plan 05-06) | closed |
| T-05-27 | Tampering | YAML document construction | high | mitigate | `yaml.safe_load` stays the only loader (`app/cv/factstore.py:65`); `grep -c "yaml.load(" app/cv/factstore.py` returns 0 (the sole occurrence is the explanatory "never reached here" comment), so a document cannot construct arbitrary Python objects (plan 05-06) | closed |
| T-05-28 | Information Disclosure | failure message | low | accept | The re-raised message is `f"{resolved}: unreadable: {exc}"` — the resolved path plus the decoder's own error text, never CV content — and it is written through structlog rather than rendered to a browser. Accepted at personal, single-operator scale. See AR-05-07 (plan 05-06) | closed |
| T-05-29 | Repudiation | the skip path's observability | low | mitigate | The unreadable-fact-store skip emits an explicit `pipeline.rank_skipped` event with `reason="fact_store_absent"` and `error=type(exc).__name__` before returning (`app/pipeline/rank.py:381-387`), so "why was nothing ranked?" is answerable from logs (plan 05-06) | closed |
| T-05-30 | Repudiation | run_repo._optional_int → RunSummary.candidate_count → queue.html #ranking-strip | medium | mitigate | A non-positive parsed count is returned as None, and the template's ratio branch requires a truthy candidates, so the strip can never assert a progress ratio the run did not produce. The exclusion is at the read boundary, so it holds for the fabricated bookkeeping-failure value, a hand-edited row and an older-build row alike. | closed |
| T-05-31 | Tampering | reason_counts_json['survivors'] parse | low | mitigate | The value is parsed by _optional_int (which returns None for absent, non-numeric AND non-positive input) and is auto-escaped by the template's existing environment; it is never interpolated into SQL and never used to build markup. A tampered 0 degrades to no ratio. | closed |
| T-05-32 | Denial of Service | queue page render path | low | mitigate | _ranking_strip keeps its never-raise guard and {} return, and _optional_int is total (its (TypeError, ValueError) guard is retained), so an unreadable or half-written run row yields a page without a ratio instead of a 500. | closed |
| T-05-33 | Information Disclosure | strip contents | low | accept | The strip renders two integers and a cap name only — no listing, CV or personal content. Accepted at personal, single-operator scale. | closed |
| T-05-34 | Repudiation | _finish → reason_counts_json['ranking'] → #ranking-strip | high | mitigate | The outcome is computed synchronously in run_pipeline and written by the single writer _finish in the same commit as status/finished_at, so the persisted reason cannot disagree with the run it describes and cannot be clobbered by the detached task (D-88). Only terminal outcomes are persisted, so a run can never claim a pass is still running when it never was. | closed |
| T-05-35 | Spoofing | the live-task probe → the running branch | medium | mitigate | running is derived from _RANKING_TASK liveness at render time and is never persisted, so an interrupted pass (crash, restart) degrades to the honest "has not completed" state instead of a permanent in-progress claim; a persisted skip marker is checked before the probe and therefore wins. | closed |
| T-05-36 | Tampering | hand-edited / older-build reason_counts_json | low | mitigate | _ranking_marker returns (None, None) for any non-mapping or non-string shape, and RunSummary.ranking_state falls through to unknown, so a corrupted marker degrades to a truthful generic sentence rather than an exception or a false claim; the value is auto-escaped by the existing template environment and never reaches SQL. | closed |
| T-05-37 | Denial of Service | queue render path | low | mitigate | _ranking_strip keeps its never-raise guard and {} return; ranking_in_progress() reads two module globals and cannot raise; the extra precheck read is one small local file per run, and its failure is caught into a reason rather than propagating. | closed |
| T-05-38 | Information Disclosure | strip copy and the persisted marker | low | accept | The strip renders a state name, a fixed human label and two integers; the marker carries no path, no CV text and no listing content, and the precheck's exception is reduced to a constant reason rather than its message. Accepted at personal, single-operator scale. | closed |
| T-05-39 | Repudiation | RunSummary.ranking_state → listing_detail.html | medium | mitigate | The sentence is derived from the persisted outcome plus the live-task probe, so the page cannot claim a cause the run did not record; the fallback branch says only that no pass has completed, which is true whenever the marker is absent. | closed |
| T-05-40 | Information Disclosure | the named CV path | low | accept | The page names Settings.cv_dir + the fact-store filename — an operator-configured path, not CV content. The failure message is never rendered: only a boolean and a fixed sentence. Accepted at personal, single-operator scale (v1 has no auth by design, D-21). | closed |
| T-05-41 | Tampering | hand-edited / older reason_counts_json | low | mitigate | The read model's marker parser and the state derivation are total, so a corrupted marker degrades to the generic "has not completed" sentence rather than raising; the reason label falls back to the raw value and then to a fixed literal, and every rendered value is auto-escaped by the existing environment. | closed |
| T-05-42 | Denial of Service | detail page render path | low | mitigate | The added work is one bounded limit=1 run read plus a pure derivation; the probe reads two module globals; no filesystem read is added on this route and no new blocking call is introduced. | closed |
| T-05-43 | Information Disclosure | fact_store_report error value → settings card / /health | medium | mitigate | The report carries the exception CLASS NAME only; the helper never renders or serialises the message, and an acceptance criterion asserts the exception message appears nowhere in the module. A YAML error's own text can echo document content, so nothing from the exception beyond its type crosses the boundary. | closed |
| T-05-44 | Repudiation | the disclosed path | high | mitigate | The path is computed once from Settings.cv_dir + rank.CV_FILENAME — the same expression the loader uses — and shared by all three surfaces, so no surface can name a path the app does not read. An acceptance criterion pins the settings card to the configured expression rather than a literal. | closed |
| T-05-45 | Spoofing | the CV status line | medium | mitigate | The line is driven by a real load attempt, not by a file-existence check, so a store that exists but cannot be decoded is reported as "no readable CV fact store" rather than as healthy; the copy deliberately never says "missing", which would be false for the unreadable and non-decodable cases. | closed |
| T-05-46 | Elevation of Privilege | CV intake | high | mitigate | No upload route, form, multipart handling or dependency is added: the truth asks for disclosure, and the CV stays a host file (D-58). This keeps the app's only input boundaries unchanged and adds no CSRF or file-write surface. | closed |
| T-05-47 | Denial of Service | settings / queue / health render paths | low | mitigate | The probe is one small local file read per render, wrapped so it can never raise, and /health reports it without affecting status, so an absent or corrupt store yields a truthful object rather than a 500 or a degraded app. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (`high`) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-05 | CV content is processed only by the user's own external opencode server; this phase adds no new outbound host, so the PROJECT.md privacy constraint (everything local in v1) holds. | plan 05-01 | 2026-09-22 |
| AR-05-02 | T-05-06 | A malformed/out-of-range model response yields no score row and is isolated per listing; one bad response cannot stop the pass or fabricate a score. | plan 05-01 | 2026-09-22 |
| AR-05-03 | T-05-08 | `rank_calls_since` is an unindexed full scan, accepted deliberately at this row count; no index migration, and the docstring forbids minting a second aggregate. | plan 05-02 | 2026-09-22 |
| AR-05-04 | T-05-14 | CV fact ids are opaque internal identifiers shown as text to the single local user behind the identity seam; they carry no personal data. | plan 05-03 | 2026-09-22 |
| AR-05-05 | T-05-20 | The Python-side score sort is bounded by `SCORE_SORT_SCAN_LIMIT` (5 000); accepted at personal scale with a documented materialisation upgrade path. (See non-blocking WR-01 note below.) | plan 05-04 | 2026-09-22 |
| AR-05-06 | T-05-25 | The queue ranking strip renders two integers and a cap-reason string only; it carries no listing, CV or personal content, so there is nothing to disclose. | plan 05-05 | 2026-09-22 |
| AR-05-07 | T-05-28 | The fact-store read-failure message carries the resolved path and the decoder's own error text, never CV content, and is written to logs rather than rendered to a browser. | plan 05-06 | 2026-09-22 |
| AR-05-08 | T-05-33 | The strip renders two integers and a cap name only — no listing, CV or personal content; accepted at personal, single-operator scale. | plan 05-07 | 2026-09-23 |
| AR-05-09 | T-05-38 | The strip copy and the persisted marker carry a state name, a fixed human label and two integers; the precheck's exception is reduced to a constant reason, never its message. | plan 05-08 | 2026-09-23 |
| AR-05-10 | T-05-40 | The detail page names an operator-configured store path, not CV content; the failure message is never rendered (only a boolean and a fixed sentence). v1 has no auth by design (D-21). | plan 05-09 | 2026-09-23 |

*Accepted risks do not resurface in future audit runs.*

---

## Threat Flags

The `## Threat Flags` sections of the four original SUMMARY files report **"None beyond the plan's threat model."** The 05-05 and 05-06 SUMMARY files carry no `## Threat Flags` section (verified by grep), and the 05-07…05-10 SUMMARY files likewise carry none (grep-verified: 0 matches each), so they introduce no unregistered flag either. No `unregistered_flag` was raised: the new `GET /listings/{id}` route, its templates, the ranking strip, the queue `sort`/`min_score` params, the weights editor, the strip's `candidate_count` read and the fact-store `(OSError, UnicodeError)` branch all map to existing threat IDs (T-05-12…T-05-47). `sort` is restricted to an allow-list (`app/web/routes.py:126`).

---

## Verification Notes (non-blocking)

Code-review (`05-REVIEW.md`) findings that touch audited surfaces are recorded here so they stay tracked without inflating `threats_open`. None is an absent declared mitigation; each declared control **is** present in the shipped code.

| Review finding | Audited threat | Assessment |
|----------------|----------------|------------|
| WR-01 — score sort silently truncates beyond 5 000 rows; `_DISMISS_LIMIT` can never trip | T-05-20 (accept, medium) | Accepted DoS trade-off stands; the truncation is *also* a correctness bug. Below the `high` block threshold. |
| WR-03 — `?min_score=nan`/`inf` passes validation and hides scored listings | T-05-19 (mitigate, medium) | Declared mitigation (no SQL interpolation, junk→None, no 500) is present; the finiteness gate is a robustness gap, not the declared tampering vector. Below threshold. |
| WR-04 — detail page Save/Hide `hx-target` element does not exist on that page | T-05-16 (mitigate, low) | The repudiation control (same event types to the same append-only endpoint) is present; the dead swap target is a UI defect. Below threshold. |
| WR-05 — `read_weights` accepts negative stored weights | T-05-17 (mitigate, high) | The declared write-boundary controls are present and verified; a poisoned stored document read path is a defense-in-depth hardening item (the write path that produces it is closed). |
| WR-06 — cap-refusal audit row counted as a spend by both ceiling and `runs.llm_calls` | T-05-07 / T-05-10 | Both controls present; over-counting inflates the ceiling conservatively (fail-safe direction), not a bypass. |
| WR-02 — non-UTF-8 `cv.yaml` escapes the D-94 skip guard | n/a (not a security threat) | **Resolved by plan 05-06:** the read failure is now a path-qualified `CvFactStoreError` and takes the documented skip path (T-05-26/T-05-29). |

*Escalation note for a later hardening pass (not phase-05 blocking): finiteness-gate `min_score` (WR-03), harden `read_weights` against poisoned stored values (WR-05), and make the score-sort truncation visible (WR-01).*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-22 | 22 (25 registered rows) | 22 | 0 | gsd-security-auditor |
| 2026-09-22 (gap-closure re-audit, 05-05/05-06) | 30 (35 registered rows) | 30 | 0 | gsd-security-auditor |
| 2026-09-23 (round-2 gap closure, 05-07…05-10) | 48 (57 declared rows across the ten PLANs) | 48 | 0 | gsd-security-auditor |

Hermetic evidence command: `.venv/bin/python -m pytest -q tests/db/test_score_repo.py tests/domain/test_rubric.py tests/pipeline/test_rank_stage.py tests/pipeline/test_rank_caps.py tests/pipeline/test_rank_optional.py tests/api/test_queue_ranked.py tests/api/test_listing_detail.py tests/api/test_ranking_weights.py tests/test_config.py tests/test_no_cdn.py tests/db/test_no_pii_columns.py` → **97 passed** (2026-09-22).

Gap-closure re-audit evidence command: `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py tests/api/test_queue_ranking_adversarial.py tests/cv/test_factstore.py tests/pipeline/test_rank_optional.py tests/pipeline/test_rank_adversarial.py tests/test_no_cdn.py` → **33 passed, 2 xfailed** (2026-09-22; the two strict xfails are the retained WR-03 and WR-05 sentinels, out of scope for the gap-closure run).

Round-2 gap-closure evidence command: `.venv/bin/python -m pytest -q tests/api/test_queue_ranked.py tests/pipeline/test_rank_optional.py tests/api/test_listing_detail.py tests/api/test_settings_page.py tests/api/test_health.py tests/cv/test_factstore.py tests/test_cv_tex_spike_docs.py tests/test_stylesheet_coverage.py` → **89 passed** (2026-09-23).

Implementation files were read-only during this audit; no file other than this SECURITY.md was written by the auditor.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-22 (initial 05-01…05-04; re-verified 2026-09-22 after 05-05/05-06 gap closure; re-verified 2026-09-23 after 05-07…05-10 gap closure)
