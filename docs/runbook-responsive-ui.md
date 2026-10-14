# Runbook — the responsive UI check (UI-06)

Phase 8 success criterion: *"The UI is usable from both a laptop and a phone
browser, with all assets vendored locally and no CDN dependency."*

Docker and a browser are absent from the agent sandbox, so this is an
**operator-run** check, not an automated test — the `docs/runbook-compose-smoke.md`
precedent. The automated half (`pytest tests/test_stylesheet_coverage.py`) proves
the committed stylesheet is the byte-identical build of its source; it cannot tell
you whether the page *looks* right at 320px. Until an operator walks the matrix
below and records the outcome, this is an **unrun verify** — recorded as unrun,
never rounded up to a pass.

## Prerequisites

- Docker Engine **≥20.10** with **Compose v2** (`docker compose`, not
  `docker-compose`).
- Port **8000** free on the host.
- The repository checked out with `compose.yml`, `Dockerfile` and `entrypoint.sh`.
- A browser with a device-toolbar / responsive mode (Firefox, Chrome or Safari
  all have one). Widths to set: **320**, **375** and **768** px.
- The health page (`/status`) lands in plan 08-04. If it is not built yet, skip
  that page's column and note it — do not mark it passed.

## Commands

```bash
# Bring the stack up (any stack already running works; this is the smoke path):
docker compose up -d --wait

# Confirm it serves before you start the viewport walk:
curl -fsS localhost:8000/health | python3 -m json.tool

# Open the queue; every other page is reachable from here:
#   http://localhost:8000/            the queue
#   http://localhost:8000/applications the applications tracker
#   http://localhost:8000/status       the health page (plan 08-04)
# A listing detail page is one queue row's `Details` link: /listings/<id>
# The run control is the queue page's `Run search now` button.
```

## What a pass looks like

Walk each journey page at each width below and record pass/fail **per cell**.

| Page | 320px | 375px | 768px |
|---|---|---|---|
| Queue (`/`) | | | |
| Listing detail (`/listings/<id>`) | | | |
| Health (`/status`) | | | |
| Run control (`Run search now`) | | | |
| Applications tracker (`/applications`) | | | |

1. **At 320 and at 375 px** the journey tables (queue, applications, health) read
   as **stacked cards**: each line is preceded by its column label (the desktop
   header word), and **no horizontal scrolling** appears anywhere on the page.
2. **At 320 and at 375 px** every tap target is comfortably finger-sized — the
   nav links, the pager buttons, the `Copy answer` button and the `History (n)`
   summary all meet the 44×44px floor.
3. **At 320 and at 375 px** the filter controls (`#queue-filters` children) and
   `Run search now` span the **full width** — nothing needs a pinch-zoom.
4. **At 768 px** the **desktop table** renders inside its scroll region rather
   than reflowing. This width proves the two regimes are exact complements and
   are not both-off at the boundary.
5. **On the admin surfaces** (criteria, merges, run history, settings) at **all
   three widths**: nothing is broken, and the merges / run-history / fit-breakdown
   tables scroll horizontally inside their labelled, keyboard-reachable regions
   (`tabindex="0"`, `role="region"`, `aria-label`).
6. **The long-name case.** Register (or rename) a source whose name is long and
   unbroken, and put a deep absolute CV path on the health page. At 320 and 375 px
   the card must **wrap the value** rather than widen the page — no horizontal
   scroll appears.

## Recording the evidence

Tick each cell above (pass/fail), and note any failure verbatim. A cell you could
not check because a page does not exist yet is recorded as **unrun**, not passed.

The second half of this phase's verification is the project's existing
**`/gsd-ui-review 08`** 6-pillar audit over the responsive surfaces (D-161), which
is the established artefact for the subjective judgement this checklist cannot
make.
