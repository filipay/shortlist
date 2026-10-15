# Phase 1: Walking Skeleton + Foundations - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-15
**Phase:** 1-Walking Skeleton + Foundations
**Areas discussed:** Probe verdict & gate, opencode endpoint & model selection, Minimal UI & assets

---

## Area selection

Presented four gray areas; user selected three. **"Sanitise & PII depth" was not selected** and is therefore not decided here — CONTEXT.md carries only the research-locked baseline (sanitise stage at the ingest boundary; PII stripped at the adapter boundary; no `emails` field on `RawListing`) and leaves exact rule enumeration to the planner.

| Option | Description | Selected |
|--------|-------------|----------|
| Probe verdict & gate | What "scraping survives" means; volume budget; where the verdict lives; Adzuna trigger | ✓ |
| opencode sidecar now? | Whether/how Phase 1 compose stands up the opencode sibling | ✓ |
| Minimal UI & assets | Phase 1 UI scope; styling pipeline; phone-first timing; HTMX | ✓ |
| Sanitise & PII depth | How aggressive ingest sanitisation/PII stripping is in Phase 1 | |

---

## Probe verdict & gate

### Q1 — What should 'scraping survives' mean?

| Option | Description | Selected |
|--------|-------------|----------|
| Threshold + written verdict | Explicit numeric signals AND a human-readable verdict spelling out the Adzuna condition | ✓ |
| Strict automated gate | Pure pass/fail on numeric thresholds; failure mechanically re-ranks Adzuna | |
| Descriptive only | Log signals, write prose, no threshold | |

**User's choice:** Threshold + written verdict (Recommended).
**Notes:** Belt-and-braces — automatable signalling plus a human-accountable conclusion. Avoids a single bad day condemning a board.

### Q2 — Probe volume & budget

| Option | Description | Selected |
|--------|-------------|----------|
| Config-driven envelope | Ceilings in config; documented recommendation 1 search/board, ≤50–100 results, once/day | ✓ |
| Minimal one-shot probe | Single run, 1 search/board, ≤50 results | |
| Multi-day soak | Daily for ~3–5 days before the verdict | |

**User's choice:** Config-driven envelope (Recommended).
**Notes:** Stays inside the personal envelope P2 defines as the ban-risk line (PITFALLS P2).

### Q3 — Where does the verdict live?

| Option | Description | Selected |
|--------|-------------|----------|
| Verdict doc + DB + /health | Dated committed doc + `runs`/`source_request_log` evidence + `probe()` status in `/health` | ✓ |
| DB + SDD report only | `runs` table + Phase 1 task report | |
| Record as a project decision | Key Decision in PROJECT.md + SRC-11 status in REQUIREMENTS.md | |

**User's choice:** Verdict doc + DB + /health (Recommended).
**Notes:** Reachable by both a human and the code.

### Q4 — What does the verdict trigger for Adzuna (SRC-11)?

| Option | Description | Selected |
|--------|-------------|----------|
| Record trigger, decide at Phase 8 | Record the exact promotion condition; no adapter work now | ✓ |
| Scaffold Adzuna adapter as insurance | Adapter skeleton in Phase 1 behind the interface | |
| No mechanical link | Human decides at Phase 8 with nothing recorded | |

**User's choice:** Record trigger, decide at Phase 8 (Recommended).
**Notes:** Matches SRC-11 being v2 and keeps Phase 1 a skeleton.

---

## opencode endpoint & model selection

The framing changed mid-area on user input: the opencode container **already exists** and is user-managed (`serve --hostname 0.0.0.0 --port 4096`), so Phase 1 must not define or pin a container.

### Q1 — Should the opencode sibling container land in Phase 1 compose?

| Option | Description | Selected |
|--------|-------------|----------|
| Sibling service, optional profile | Define + pin + healthcheck behind a compose profile | |
| Sibling service in the default stack now | `up` brings both containers | |
| Defer opencode to Phase 3 | App-only compose in Phase 1 | |

**User's choice (free text):** "Actually the container already exists (you are in the container, command: `serve --port 4096 --hostname 0.0.0.0`). So basically we assume that the endpoint will be available."
**Notes:** No opencode service in `compose.yml`. The initial three options were built on a wrong premise and were superseded.

### Q2a — How does the app container reach the user-managed opencode server?

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable base URL via host-gateway | `OPENCODE_BASE_URL` default `http://host.docker.internal:4096` + `extra_hosts` | ✓ |
| Host network mode | `network_mode: host` | |
| Pure external config, no default | User supplies URL per environment | |

**User's choice:** Configurable base URL via host-gateway (Recommended).

### Q2b — How much model discovery/pinning belongs in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Config seam + discovery now | Discovery read + `OPENCODE_MODEL` config, no LLM call | ✓ |
| Config keys only, discovery in Phase 3 | Bare config keys, model listing later | |
| Model-picker UI in Phase 1 | Persisted model-selection screen | |

**User's choice (free text):** "Since you're in the container, I don't think you'll be able to query yourself?? If you can find out the models, however these could differ based on the users subscription to open code."
**Notes:** The premise was tested directly. The server **is** reachable from inside the container and returns models. Findings recorded below; the user then confirmed the discovery-read + env-pin shape.

**Investigation performed (probed live, 2026-09-15):**
- `GET /global/health` → `{"healthy":true,"version":"1.18.29"}`, listening `0.0.0.0:4096`.
- `GET /config/providers` → 200, ~29 KB, returns the **subscription-scoped configured set**: `opencode-go` (27 models: `deepseek-v4.1-flash`, `qwen3.7-max`, `glm-5.2`, `kimi-k2.6`, `longcat-2.0`, `minimax-m3`, …) and `opencode` (7 models).
- `GET /provider` → 200, ~6 MB: full vendor catalogue (217 providers, ~7,756 models). **Not** the user's entitlement; unsuitable as a discovery source.
- ⚠️ `/config/providers` returns the provider API key in plaintext — logged as a security constraint (extract IDs only; never persist/log the response).
- `/doc` → OpenAPI 3.1; both `/api/*` and legacy top-level aliases exist.

### Q2c — Should Phase 1 pin a default model, or require the user to choose?

| Option | Description | Selected |
|--------|-------------|----------|
| Documented default, overridable | Cheap default (e.g. `deepseek-v4.1-flash`) in config, overridable via `.env` | ✓ |
| Require explicit selection | No default; Phase 3 fails loud until set | |
| Default to a premium model | Most capable discovered model by default | |

**User's choice:** Documented default, overridable (Recommended).
**Notes:** Spend begins only at Phase 3; Phase 3 records model+version per call (PITFALLS M9).

### Q3 — How is opencode access configured?

| Option | Description | Selected |
|--------|-------------|----------|
| Base URL + optional password via .env | `OPENCODE_BASE_URL` + optional `OPENCODE_SERVER_PASSWORD`, uncommitted | ✓ |
| No auth assumed | No credential handling | |
| Docker secrets / runtime env-file | Strongest hygiene, more friction | |

**User's choice:** Base URL + optional password via .env (Recommended).
**Notes:** SRC-06's "no credential path" is read as *portal credentials*; a local LLM server credential is config and explicitly allowed.

### Q4 — Startup behaviour when opencode is absent/unhealthy?

| Option | Description | Selected |
|--------|-------------|----------|
| Degraded-tolerant | App boots without it; `/health` reports `unreachable` | ✓ |
| Fail fast | App refuses to start unless opencode is healthy | |

**User's choice:** Degraded-tolerant (Recommended).

---

## Minimal UI & assets

### Q1 — How much UI does Phase 1 ship?

| Option | Description | Selected |
|--------|-------------|----------|
| List + Run + health strip | List + empty state + count + Run button + polling + per-source health strip | ✓ |
| List + Run, health via /health JSON | No health UI surface until Phase 2/8 | |
| Bare list only | No UI run trigger (fails RUN-01) | |

**User's choice:** List + Run + health strip (Recommended).
**Notes:** SRC-07 says the user *can see* per-source health, so it needs a surface.

### Q2 — Styling pipeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Tailwind CLI build, vendored output | Tailwind 4 CLI at image build, local static output, no CDN | ✓ |
| Vendor prebuilt CSS (Pico) | Prebuilt stylesheet now, Tailwind later | |
| Hand-written minimal CSS | Custom minimal CSS | |

**User's choice:** Tailwind CLI build, vendored output (Recommended).
**Notes:** Establishes the styling system Phase 5's ranking UI will need; avoids a later migration.

### Q3 — Phone-first foundation now or Phase 8?

| Option | Description | Selected |
|--------|-------------|----------|
| Phone-first foundation now | Mobile-first layout basics from Phase 1; UI-06 still Phase 8 | |
| Desktop-first, phone in Phase 8 | Build desktop-comfortable; phone pass in Phase 8 | ✓ |

**User's choice:** Desktop-first, phone in Phase 8.
**Notes:** ⚠️ **Direct conflict with PROJECT.md** ("Phone-first responsive design; primary access is a phone") and REQUIREMENTS.md Out-of-Scope ("Desktop-first design — Primary access is a phone"). The conflict was raised explicitly and the user confirmed desktop-first for Phase 1. CONTEXT.md records it as a scoping decision with a Phase 8 payoff rather than silently treating it as consistent with PROJECT.md.

### Q4 — HTMX/Alpine in Phase 1, or plain forms?

| Option | Description | Selected |
|--------|-------------|----------|
| Vendor HTMX + Alpine now | Vendored locally; HTMX drives run trigger + polling | ✓ |
| Plain forms now, HTMX in Phase 2 | Full-page reloads in Phase 1 | |

**User's choice:** Vendor HTMX + Alpine now (Recommended).
**Notes:** Proves UI-07 (all assets vendored) and sets the Phase 2 interaction pattern.

---

## the agent's Discretion

- **PII rule enumeration** — not selected for discussion; the baseline is locked (strip at adapter boundary, never store, no `emails` field) but the exact regex catalogue / hashing-vs-dropping is left to the planner. Injection-pattern rules are an additive Phase 2 task.
- **Probe document naming/location, health-strip layout, and the `/models` vs `/health`-embedded discovery surface** are left to the planner within the constraints captured in CONTEXT.md.
- **Degradation semantics for a partially-failed run** (one board `blocked`, one `ok`) is left to the planner, bounded by SRC-05.

## Deferred Ideas

- Adzuna adapter (SRC-11) — promotion decided at Phase 8 against the recorded Phase 1 probe condition.
- Model-picker UI — deferred; discovery + `OPENCODE_MODEL` config only in Phase 1.
- `_INJECTION_PATTERNS`-style sanitisation rule set — Phase 2, Apache-2.0 attributed pattern-copy.
- Model + version recording per LLM call — Phase 3.
- Phone-first layout pass (UI-06) — Phase 8.
- Scheduling (RUN-05/06, PLAT-06) — Phase 8.
- Authentik OIDC / multi-user (PLAT-07) and MCP server (PLAT-08) — future milestone.
