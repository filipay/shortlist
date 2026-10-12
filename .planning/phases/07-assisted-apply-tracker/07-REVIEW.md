---
phase: 07-assisted-apply-tracker
reviewed: 2026-10-12T15:20:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - app/domain/schemas/_coerce.py
  - app/domain/cv.py
  - app/domain/schemas/screening.py
  - app/domain/schemas/ranking.py
  - app/llm/opencode_server.py
  - app/api/applications.py
  - app/api/apply.py
  - app/web/templates/html/_application_row.html
  - app/web/templates/html/_screening_drafts.html
  - assets/tailwind/input.css
  - static/vendor/app.css
  - tests/test_stylesheet_coverage.py
  - tests/domain/test_coerce.py
  - tests/domain/test_screening_schema.py
  - tests/llm/test_salvage.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 07: Code Review Report (re-review after 07-13 / 07-14 gap closure)

**Reviewed:** 2026-10-12T15:20:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

This is the re-review triggered by the two gap-closure plans that closed the previous
report's findings:

- **07-13 (CR-01)** — reconciled `assets/tailwind/input.css` with the shipped
  `static/vendor/app.css` and added three guards to `tests/test_stylesheet_coverage.py`.
- **07-14 (WR-01)** — restricted `unwrap_single_key_mapping` to the literal
  `WRAPPER_KEY = "item"`, bounded it against self-reference, and wired
  `TailoringPatch.ops` / `.gaps` / `.suggestions` through `coerce_mapping_list`.

**Both prior findings are genuinely closed — verified, not taken on trust:**

- **CR-01 closed.** A fresh build of `input.css` with the pinned CLI
  (`./node_modules/.bin/tailwindcss` v4.3.3, the exact `Dockerfile:19` command) is
  **byte-identical** to the committed `static/vendor/app.css` (`cmp` exits 0). The
  source carries every one of the 217 literal template class tokens (0 missing in
  source, 0 missing in artifact, 0 present-in-artifact-only), plus all eleven
  dynamic-suffix badge values. The new Node-free source guard and the byte-identity
  guard both pass; the guards have non-vacuous companion assertions. `static/vendor/app.css`
  is one minified line and no rule was hand-appended.
- **WR-01 closed.** `{"nope": ["bul/x/1"]}`, `{"items": …}`, `{"value": …}` and
  `{"data": …}` now all raise `ValidationError`; `{"item": …}` and nested
  `{"item": {"item": …}}` still unwrap; the held-out salvage fixture (4 answers,
  17/1/0/3 evidence ids) still validates. The two scalar-value false-name tests were
  replaced, not supplemented. `TOLERATED_SCHEMA_ERRORS` is byte-unchanged
  (`{"missing", "int_parsing"}`); `extra="forbid"` is intact; the tailoring patch's
  three top-level lists share the helper.

Test/lint of record re-run with the provisioned interpreter
(`/tmp/opencode/gsdvenv13/bin/python`, 3.13.16 / pytest 9.1.1): the scoped lanes are
green (coerce + screening + stylesheet = 34 passed; salvage + patch_ops +
import_discipline + cv_ids = 63 passed) and `ruff check app/domain` is clean.

One residual defect survives in the WR-01 fix: the self-reference bound covers only
the direct instance, and the docstring states a guarantee the code does not deliver
(WARNING, below). Two low-severity notes follow.

## Warnings

### WR-02: The self-reference bound misses a mutual cycle, and the docstring claims it cannot hang

**File:** `app/domain/schemas/_coerce.py:38-45` (loop), docstring `:35-36`; test `tests/domain/test_coerce.py:146-151`
**Severity:** medium
**Issue:** The loop breaks only when the *inner value is the outer Mapping*
(`if inner is value: break`). That covers direct self-reference
(`d["item"] = d`) but not a two-node cycle:

```python
a = {}; b = {"item": a}; a["item"] = b   # a → b → a
unwrap_single_key_mapping(a)             # never returns (observed: 20s timeout, exit 124)
```

The helper's docstring asserts the opposite — "The loop also stops when the inner value
IS the outer Mapping, so a caller-constructed self-reference **cannot hang** the caller"
— which is a false guarantee in prose (CONVENTIONS rule 6). The fix's own test pins the
*instance* (direct self-reference) and not the *failure class* (any cyclic single-key
mapping), which is precisely the trap CONVENTIONS rule 4 names. Reachability is low
(wire payloads are `json.loads`-derived and cannot be cyclic; `T-07-14-03` rated it low),
so this is not a blocker — but the helper is exported in `__all__` and the docstring
invites a caller to construct exactly this input.

**Fix:** Bound the loop by visited-identity, not by single-step identity, and keep the
prose honest:

```python
def unwrap_single_key_mapping(value: Any) -> Any:
    seen: set[int] = set()
    while isinstance(value, Mapping) and len(value) == 1 and id(value) not in seen:
        key, inner = next(iter(value.items()))
        if key != WRAPPER_KEY:
            break
        seen.add(id(value))
        value = inner
    return value
```

Then replace the direct-instance test with a parametrised cyclic case (direct and
two-node) asserting termination, and drop the absolute "cannot hang" wording for
"terminates on any cycle reachable through the literal wrapper key".

## Info

### IN-03: `_coerce_ops` docstring names the wrong refusal route for `ops`

**File:** `app/domain/cv.py:531-538`
**Severity:** low
**Issue:** The docstring says a non-`item` single-key mapping on `ops` is "refused by
`PatchOp`'s discriminated union — `extra="forbid"` survives". For `ops` the refusal is
the *discriminator* (`Unable to extract tag using discriminator 'op'`), not
`extra="forbid"`; the two are separate mechanisms and the sentence fuses them. It is not
a false guarantee (both refuse), but it misstates which check fires. `coerce_mapping_list`'s
own docstring correctly attributes `extra="forbid"` to the `list[Model]` route.
**Fix:** Say the non-`item` mapping becomes one item and is refused by the discriminated
union's missing `op` tag (a `PatchOp` member is `extra="forbid"`, but that is not the
check that fires here).

### IN-04: The byte-identity guard is unarmed wherever the Tailwind CLI is absent

**File:** `tests/test_stylesheet_coverage.py:232-265`
**Severity:** low
**Issue:** `test_the_committed_stylesheet_is_the_build_of_its_source` visibly
`pytest.skip`s when `node`/`node_modules/.bin/tailwindcss` is absent (it was `skipped`
in the Node-less default lane). This is the intended, documented trade-off, and the
Node-free source-coverage guard still fails closed on a *dropped* class — but it does
**not** catch a hand-edit to `static/vendor/app.css` that adds or changes a rule without
dropping any template class (the artifact would stay class-complete yet diverge
byte-wise). That divergence would be invisible in a CI lane that has no Node toolchain.
The deployed image is unaffected (`Dockerfile:19` rebuilds from source and
`Dockerfile:116` ships the rebuild), so this is a dev-tree/test-coverage gap only.
**Fix:** No change required. If the guarantee is wanted in CI, run the byte-identity
assertion in a lane that installs the pinned CLI (or assert the CLI version in the skip
message) rather than loosening it.

---

## Prior findings — closure status

| Prior ID | Prior severity | Status | Evidence |
|----------|----------------|--------|----------|
| CR-01 (stylesheet not reproducible; Docker ships unstyled UI) | critical/blocker | **CLOSED** | Fresh pinned 4.3.3 build is byte-identical to committed `static/vendor/app.css`; all 217 literal classes + 11 dynamic suffixes present in source and artifact; guards added and green. |
| WR-01 (arity-only unwrap; false "unknown key fails loudly") | warning | **CLOSED** | Key restricted to literal `"item"`; unknown-key-with-list, `items`/`value`/`data` all raise; scalar false-name tests replaced; docstrings match code. Residual cycle issue filed above as WR-02. |
| IN-01 (`TailoringPatch` lists uncoerced) | info | **CLOSED** | `ops`/`gaps`/`suggestions` route through `coerce_mapping_list`; `extra="forbid"` unchanged; verified `None`→`[]`, bare mapping→one item, non-`item`→refused. |
| IN-02 (unbounded unwrap loop) | info | **PARTIAL** | Direct self-reference bounded and tested; mutual cycle still hangs — see WR-02. |

---

_Reviewed: 2026-10-12T15:20:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
