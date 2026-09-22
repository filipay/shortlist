---
phase: "05"
slug: "ranking-core-value"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-22"
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS L1** (grep-level presence). The register was authored at plan time in all four PLAN files, so per the secure-phase short-circuit (`threats_open: 0`, `register_authored_at_plan_time: true`, `asvs_level: 1`) L1 presence verification is sufficient. `security_block_on = high`.

**Scope audited:** LLM ranking pipeline (`app/pipeline/rank.py`), detached ranking lifecycle (`start_ranking_task`), spend caps (`app/config.py`, `app/db/repositories/llm_call_repo.py`), ranking-weights write path (`app/api/settings.py`, `app/db/repositories/ranking_config_repo.py`), new `GET /listings/{id}` route (`app/api/listings.py`, registered `app/main.py:63`), and the new HTML/Jinja templates (`listing_detail.html`, `queue.html`, `queue_list.html`, `settings.html`, `_listing_row.html`).

**Register hygiene note:** `T-05-SC` is declared once in each of the four PLAN files with a per-plan scope; there are 21 unique numbered threats (`T-05-01`…`T-05-21`) plus the four `T-05-SC` occurrences — 25 registered rows, 22 unique threats. The four `T-05-SC` rows are presented as one row below.

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
| T-05-SC | Tampering (supply chain) | npm/pip/cargo installs (05-01…05-04) | high | mitigate | No package installed by this phase: `pyproject.toml`/`requirements`/`uv.lock` unchanged in every phase-5 commit (last dependency change is phase-04 `320e2e2`); vendored-assets guard `tests/test_no_cdn.py` | closed |
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

*Accepted risks do not resurface in future audit runs.*

---

## Threat Flags

The `## Threat Flags` sections of all four SUMMARY files report **"None beyond the plan's threat model."** No `unregistered_flag` was raised: the new `GET /listings/{id}` route, its templates, the ranking strip, the queue `sort`/`min_score` params, and the weights editor all map to existing threat IDs (T-05-12…T-05-21). `sort` is restricted to an allow-list (`app/web/routes.py:126`).

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
| WR-02 — non-UTF-8 `cv.yaml` escapes the D-94 skip guard | n/a (not a security threat) | Availability/observability bug in an optional stage; tracked in the code review. |

*Escalation note for a later hardening pass (not phase-05 blocking): finiteness-gate `min_score` (WR-03), harden `read_weights` against poisoned stored values (WR-05), and make the score-sort truncation visible (WR-01).*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-22 | 22 (25 registered rows) | 22 | 0 | gsd-security-auditor |

Hermetic evidence command: `.venv/bin/python -m pytest -q tests/db/test_score_repo.py tests/domain/test_rubric.py tests/pipeline/test_rank_stage.py tests/pipeline/test_rank_caps.py tests/pipeline/test_rank_optional.py tests/api/test_queue_ranked.py tests/api/test_listing_detail.py tests/api/test_ranking_weights.py tests/test_config.py tests/test_no_cdn.py tests/db/test_no_pii_columns.py` → **97 passed** (2026-09-22).

Implementation files were read-only during this audit; no file other than this SECURITY.md was written by the auditor.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-22
