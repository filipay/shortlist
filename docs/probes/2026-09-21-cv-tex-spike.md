# CV `.tex` decomposition spike — Phase 4

**Status:** PARTIAL

**Date opened:** 2026-09-21
**Instrument:** `app/cv/import_tex.py` (the bounded parser and its report),
`scripts/cv-tex-spike.sh` (the re-runnable entry point), the `latex` lane in
`tests/latex/`
**Command that produced every count below:**

```bash
bash scripts/cv-tex-spike.sh tests/fixtures/cv/awesomecv_standin.tex /tmp/cv-spike-draft.yaml
```

**Engine:** Tectonic **0.17.0**, pinned by `Dockerfile`'s `ARG TECTONIC_VERSION`
and checksum-verified in the same layer. The installed binary's own `--version`
output was **not observed in this environment**: the binary lives only inside the
image and Docker is unavailable here. Likewise, the cached-only flag and the
untrusted-mode option were **not read from the installed binary's own help** —
D-75's implementation-time confirmation is outstanding, and the exact command that
performs it is:

```bash
docker compose run --rm app tectonic --help
```

**Fallback measurement (D-76):** **not taken.** `Dockerfile.texlive` has not been
built in this environment, so the fallback is **not** claimed as available.

**Stand-in caveat:** the real document is not in this repository by design
(D-58). Every number below measures the committed stand-in; none of them measures
anyone's CV.

---

## 1. What the stand-in is

A synthetic document, committed at `tests/fixtures/cv/awesomecv_standin.tex`,
built from the assumed package set plus its own `\newcommand` entry macro, and
the macro-heavy case on purpose so the measurement is conservative (D-61). No
third-party template is vendored. The assumed package set is named as package
names only: `fontspec`, `geometry`, `tabularx`, `paracol`, `enumitem`,
`titlesec`, `hyperref`.

## 2. What the stand-in PROVES

Separated explicitly from §3. Only the first item below was measured in this
environment; the rest are asserted by committed build steps that this environment
cannot run, and each says so.

**(a) Parser behaviour on macro-encoded structure — MEASURED.** The bounded
parser learned the entry macro's arity from the preamble declaration and read its
call site, producing the counts in §2.1. Evidence: the command above.

**(b) Bundle coverage for the assumed package set — ASSERTED BY A COMMITTED
BUILD STEP, NOT RE-MEASURED HERE.** The image build compiles the committed
fixture through the engine as a cache prime, so a successful build is the
evidence. This environment has no engine and no container runtime, so the build
step was not run here; the one-command check per package is named in §4.

**(c) The offline compile path works — ASSERTED BY THE COMMITTED LANE, NOT
RE-MEASURED HERE.** The gate is `docker compose run --rm app pytest -m latex`,
which this environment cannot run. The hermetic half of the lane (fixed argv,
failure-as-value, skip-not-deselect) is covered in its own plan's summary.

**(d) The font-resolution form — DESIGN CHOSEN, NOT MEASURED HERE.** The fixture
declares its main font by filename with an explicit face map, which is the form
that resolves in both engines; the by-symbolic-name form is committed as a
commented block. Which of the two the installed engine accepts was **not**
measured here.

### 2.1 The measured counts (traceable to the command above)

| Metric | Value |
|--------|-------|
| sections parsed | 2 |
| entries parsed | 1 |
| bullets parsed | 3 |
| lines scanned | 75 lines |
| unresolved section headings | 0 |
| truncated | no |
| packages requested | 7 (`fontspec`, `geometry`, `tabularx`, `paracol`, `enumitem`, `titlesec`, `hyperref`) |

The names the parser reported without guessing (count `1` each unless noted),
with their line numbers: `setmainfont`, `geometry`, `hypersetup`, `titleformat`,
`\section` (2), `large`, `bfseries` (2), `titlespacing`, `center`, `LARGE`,
`href`, `tabularx`, `textwidth`. These are LaTeX command and environment tokens
only.

The emitted draft validated through the fact store (`app/cv/factstore.py`) — the
same validator the real run uses — and an entry whose date argument cannot be
parsed fails that validator loudly, naming the path. Unresolved is therefore
distinguishable from empty.

## 3. What the stand-in does NOT prove

- It does **not** prove that the real document decomposes.
- It does **not** prove bundle coverage for a preamble nobody has seen.
- It does **not** prove the real document's page count.
- It does **not** prove whether the real document needs the fallback engine.
- It does **not** prove the installed engine's flag names (D-75).

## 4. UNRESOLVED — blocked on the real document

The trigger. This document remains **PARTIAL** until the numbers from the real
document are recorded here. The steps, in order:

1. Create the host directories and place the document:
   ```bash
   mkdir -p cv artifacts
   # place the real LaTeX CV at cv/base.tex
   ```
2. Run the spike against it:
   ```bash
   bash scripts/cv-tex-spike.sh
   ```
   The default source is `cv/base.tex`; the draft is written to a separate review
   path (`cv/cv.draft.yaml`), never back over the source and never over
   `cv/cv.yaml`.
3. Append the resulting counts and the unresolved names to **this document**.
   Counts, names, versions, commands and unit-suffixed durations only.
4. Run the bundle-coverage check once per preamble package:
   ```bash
   docker compose run --rm app tectonic -X bundle search <package>
   ```
   Record which packages the bundle holds here.
5. Confirm the engine's own option names (D-75):
   ```bash
   docker compose run --rm app tectonic --help
   ```

**STATE.md's blocking unknown #1 remains open** until these numbers are recorded
here. The trigger command named above is the one `scripts/cv-tex-spike.sh`
implements.

## 5. The fallback measurement (D-76)

**Not taken.** No TeX Live image has been built here, so no image size, build
duration, argv or page count is recorded. The fallback's "available" claim is
therefore **not** made; it becomes available only when this section carries the
four measured inputs. The one-off build and switch are documented in
`docs/runbook-latex-compile.md`.

## 6. Risks acknowledged

- **The real document may not decompose.** The codebase's answer is to hand-author
  the fact store once, as the bounded parser's curation step; the risk is
  unmeasurable by design here.
- **The preamble may carry primitives the engine rejects.** The codebase's answer
  is preamble sanitisation for the known pdfTeX-only primitives, with the fallback
  engine as the answer for anything else.
- **A font may resolve under one engine and not the other.** The codebase's answer
  is the by-filename declaration, which was chosen for exactly that reason (though
  not measured here).

## 7. Nothing from the real document

This document is **committed**, so it carries counts, package names, versions,
commands and unit-suffixed durations only. No CV content and no personal detail
may ever be added to it. The same rule applies to
`docs/runbook-latex-compile.md`.

---

*Phase: 04-cv-fact-store-latex-compile-spike · Plan: 04-05*
*Opened: 2026-09-21 · Marker: PARTIAL (stand-in measured; real-document trigger named)*
