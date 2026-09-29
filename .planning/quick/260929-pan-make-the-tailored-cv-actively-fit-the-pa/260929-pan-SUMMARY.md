# 260929-pan — make the tailored CV actively fit the page budget

## What shipped

`meta.max_pages` is now load-bearing: after the first compile, a tailored CV whose
page count exceeds it drops its lowest-value surviving bullet, re-renders and
recompiles until it fits, the candidate list is exhausted, or `MAX_PAGE_TRIM_PASSES`
is hit. Every removal is a reasoned `DropBullet` in the final patch and change log,
and the compile response names each dropped bullet and its reason.

- `app/domain/cv.py` — pure `next_page_trim(plan, patch, *, max_pages)` selector over
  the plan's own carried order (bottom of the document first), plus
  `PAGE_TRIM_REASON_TEMPLATE`; both in `__all__`.
- `app/pipeline/tailor.py` — the bounded render→compile→drop loop in
  `compile_tailored`, `MAX_PAGE_TRIM_PASSES = 6`, final-patch/change-log persistence,
  and a Layer-1 re-verify of the final trimmed plan.
- `app/api/tailoring.py` — `_compiled_fragment(listing_id, record)` discloses every
  `drop_bullet` row in the recorded change log.

## Commits

- `946e919` feat(260929-pan): trim an over-budget tailored CV by whole bullets
- `aa647ce` test(260929-pan): pin the trim bound, identity, exhaustion and fallback edges
- `59ed706` test(260929-pan): pin the multi-trim audit and the compile disclosure

## Verification

- `python -m pytest -q` → 1483 passed, 14 deselected, 2 xfailed.
- `python -m ruff check` and `ruff format --check` on all six changed files → clean.

## Notes / deviations

- Pre-existing formatting drift: the checked-in `app/domain/cv.py`,
  `app/pipeline/tailor.py` and `app/api/tailoring.py` were not format-clean under the
  pinned `ruff==0.16.7`, so the tracer commit also carries the formatter's mechanical
  collapse of untouched expressions in those files.
- The HTTP compile-response disclosure is asserted in `tests/api/test_tailoring_review.py`
  (Task 3's declared file), not in Task 1.
- No new dependency, DB column, migration, Settings field or golden-baseline change.
