# Conventions

Durable rules that emerged from real defects. These are read by every agent via AGENTS.md — follow them when writing or reviewing code, not just when a phase explicitly asks.

---

## Writing and reviewing verification checks

Origin: phase 06 (2026-09-25). A gap-closure plan reported `_entry_lines` "closed" when the defect had only been narrowed. The region anchor in `app/verify/numbers.py` matched an entry's org AND title as naked substrings over lossy extracted PDF text; a body bullet naming a later employer hijacked the region start, so a **valid** CV hard-failed the blocking `metric_containment` check and became un-previewable and un-downloadable. Code review, the Nyquist audit, and the verifier each caught it independently after the plan was marked done.

### Rules

1. **Anchor structurally, never lexically.** Region, section, and entity boundaries must come from a discriminator that free text cannot accidentally satisfy — a date-range token, a separator, an index into the structured model. Substring containment over extracted or LLM-produced text is not an anchor. Prefer `app/domain/cv.py`'s structured entries over re-parsed text entirely (deferred ideal, but it is the end state to move toward).

2. **Fail closed, visibly.** When a check cannot locate what it needs, surface a `warn` in the check report. Never let an unlocatable region degrade to an empty candidate set and a silent skip — a silent skip on a fabrication detector is a false negative, which is the failure the check exists to prevent.

3. **Every gap-closure fix adds a fixture with the finding's literal repro string.** Not a paraphrase, not a related shape. The fixture must reproduce the reported input and assert the corrected behavior. If the fix cannot produce a failing case without it, the fix is not tested.

4. **Test the failure class, not the instance.** Add a property/parametrized test that mutates free text to embed other entities' identifiers (another employer's name, another entry's title) and asserts the checker still passes. One regression test that names only half the collision (org but not title) gives false confidence — that is exactly how the round-2 miss survived a green suite.

5. **The fix author does not certify closure.** A reviewer or verifier owns the "closed" verdict. Run a scoped code review over the changed files after each gap-closure fix, before reporting the finding closed.

6. **Watch for false guarantees in prose.** A docstring or comment claiming a guarantee the code does not deliver suppresses scrutiny. If a check has a known trade-off (e.g. an input shape it handles conservatively), make it a runtime-visible warning, not a comment and a test name.

7. **Asymmetric verification pressure is a known bias.** A fail-closed detector attracts almost all test effort on "does it catch the bad thing?" and almost none on "does it accept valid input?" The false-positive surface is where a blocking check does real damage. Budget test effort for both directions explicitly.

### Scope

These rules apply to every check that compares model-produced free text against structured project data: `app/verify/numbers.py`, `app/verify/grounding.py`, `app/verify/plan_checks.py`, `app/verify/text_checks.py`, and anything added later.
