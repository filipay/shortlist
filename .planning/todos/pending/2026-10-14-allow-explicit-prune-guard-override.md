---
created: 2026-10-14T23:50:43.313Z
title: Allow an explicit, non-default override of two prune guards
area: api
severity: minor
files:

  - app/db/repositories/retention_repo.py
  - app/api/settings.py
  - app/web/templates/html/settings.html

audit_acknowledged:
  milestone: v1.0
  at: 2026-10-15
---

## Problem

Raised by the user during the phase-08 prune walk: "i should be able to delete all regardless
of already existing work, maybe not by default tho".

The `Kept regardless` line (D-165) is unconditional. Its four guards are:

- (a) the newest `RUN_FLOOR` (=50) runs — the source-health badge and the Adzuna promotion
  verdict read that window;
- (b) the `llm_calls` spend ledger — it backs the cost ceilings;
- (c) CVs attached to an application — the user's record of what was actually sent;
- (d) each listing's newest verified CV.

## Solution

TBD. **Scope decided by the user on 2026-10-14** — honour it exactly:

- An explicit, non-default override MAY bypass **(a)** the newest-runs window and **(d)** the
  newest-verified-CV guard. Both are rebuildable by re-running the pipeline, so losing them is
  recoverable.
- Guards **(b)** the `llm_calls` ledger and **(c)** application-linked CVs stay **ABSOLUTE** —
  they are the audit trail and must remain undeletable through this surface.

Direction:

1. Thread an explicit opt-in flag through both `preview` and `delete` so the dry run can show
   exactly what the override *adds* (count + size delta), never silently.
2. Require a typed confirmation (the existing `RESET_CONFIRM_TOKEN` pattern) — never a checkbox
   default-on.
3. The audit line must name the override and which guards were lifted.
4. Tests: the override lifts (a) and (d) only; (b) and (c) survive an override attempt; the
   default path is unchanged.
