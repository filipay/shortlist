---
created: 2026-10-14T23:50:43.313Z
title: Add a prune-all action across every category
area: ui
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

Raised by the user during the phase-08 prune walk: "also no option for prune all?"

That is by design today (D-163): a prune is **one category at one age**, so
`PRUNE_CATEGORIES = {"runs", "artifacts", "source_request_log", "listings"}` must be cleared
with four separate preview/confirm round trips. There is no single action that clears
everything, and the panel never lists the four categories — the user had to ask "what can i
prune?". So the surface is both narrow and under-described.

## Solution

TBD. Direction:

1. List the four categories (with their nouns) on the panel so "what can I prune" is answered
   without asking.
2. Add an explicit "all categories" option that runs the *same* per-category predicates the
   single-category path uses (never a new query — the count-shown-equals-count-removed property
   must hold per category), and reports one combined count/size plus one audit line naming each
   category's contribution.
3. Keep all four `Kept regardless` guards in force; the "all" path must not weaken them.
