# Deferred items — phase 07

Out-of-scope discoveries logged during execution (not fixed here; see the plan's
SCOPE BOUNDARY rule).

## 07-11

- **`assets/tailwind/input.css` has drifted from `static/vendor/app.css` since phase 5.**
  `input.css` was last modified in phase 5 (`dd70585`); the built artefact was updated
  through phase 7 (`b82a8e2`). Every phase 6/7 rule (`.badge-score*`, `.badge-stage-*`,
  `.next-overdue`, `.apply-*`, `.answer-*`, `.htmx-indicator`, `.cv-delete`,
  `input[type=file]`, `.badge-flagged`, `.cv-status`, …) lives only in the hand-appended
  block of `static/vendor/app.css` and is absent from `input.css`. Consequence: any full
  Tailwind rebuild (including the Dockerfile's `assets` stage) silently drops those rules
  and fails `tests/test_stylesheet_coverage.py`. Pre-existing; fixing it is a much larger
  change than this gap-closure plan, so 07-11 hand-appended its three `tracker-*` rules to
  the built artefact instead of rebuilding. Upgrading the danger: reconcile `input.css`
  with the built output (move the phase 6/7 component rules into `input.css`) before the
  next full rebuild.
