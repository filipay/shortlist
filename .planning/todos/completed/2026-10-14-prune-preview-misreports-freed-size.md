---
created: 2026-10-14T23:50:43.313Z
title: Prune preview misreports the freed disk size
area: ui
severity: major
files:
  - app/db/repositories/retention_repo.py:447
  - app/api/settings.py:959
  - app/web/templates/html/settings.html:338
---

## Problem

Found during the operator walk of the phase-08 prune surface (UAT item 4). The preview
read:

    This will delete 4 artifacts · 117043.0 GB.

~117 TB for four tailored CVs is impossible — the entire `artifacts/` tree on the host is
**460 KB** (largest single file 29,702 B). The surface is lying about its own impact, which
is the failure mode this project's conventions exist to prevent.

The formatter is provably correct: `_human_size` divides by 1024 per iteration and returns
`f"{value:.1f} {unit}"`, so `size_display` = `117043.0 GB` means `size_bytes` ≈ 1.2567e14.
The blame is therefore upstream, in the only `st_size` site in the codebase:

- `retention_repo._size_inside(raw, root)` (line ~447) returns `resolved.stat().st_size` for
  any path that resolves inside the artifacts root. It performs **no `S_ISREG` check**, so a
  directory, a special/pseudo file, or a filesystem that reports a bogus `st_size` (Docker
  Desktop's virtiofs/9p bind mounts are known to do this) silently produces a meaningless
  total that is then presented as a fact.
- `retention_repo.preview()` sums those values with no sanity bound.
- Root resolution: `app/api/settings.py:_prune_root()` → `Path(settings.artifacts_dir).resolve()`;
  `artifacts_dir` defaults to `/artifacts` (`app/config.py:189`) and `compose.yml:14` bind-mounts
  `./artifacts:/artifacts`. On the host the stored container-absolute paths
  (`/artifacts/<listing>/cv-<hash>.tex`) do not exist, so the preview reports `0 B` there — the
  bad number is only observable inside the container. That is why it was not caught by any test.

Reproduce inside the container:

    docker compose exec app sh -lc 'find /artifacts -type f -printf "%s\t%p\n" | sort -rn | head -20'

Compare that list against the reported total; the first path whose `%s` is astronomically
larger than its `ls -l` size (or a non-regular file) is the culprit.

## Solution

TBD. Candidate direction:

1. Measure only regular files — gate `_size_inside` on `stat.S_ISREG(resolved.stat().st_mode)`
   and count anything else as *unmeasured* (already reported through `missing_files`, which the
   panel can surface as "N paths not measured").
2. Consider a plausibility bound (e.g. clamp against `shutil.disk_usage(root).total`) so a
   single lying `st_size` can never produce a number larger than the filesystem that holds it.
3. Add a test with a **directory** and a **FIFO/special file** as stored `tex_path`/`pdf_path`
   values, asserting neither is counted, plus a test with a stubbed `st_size` beyond the disk
   total asserting it is clamped or reported, never printed as a fact.

---

Resolved by plan 08-06 (commits 2783c65, 1df348a): `_size_inside` is gated on `stat.S_ISREG`, unmeasurable paths increment `missing_files`, the preview appends `· N path(s) not measured`, and a structlog trail names every not-measured path. The operator re-walked the surface and accepted it (08-UAT.md item 4).
