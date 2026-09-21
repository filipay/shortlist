#!/usr/bin/env bash
#
# cv-tex-spike.sh — the D-60 measurement for the real CV.
#
# Turns the human's LaTeX CV into a DRAFT fact store plus a report of everything
# the bounded parser could not resolve. It never writes over the document it read
# and never writes over cv/cv.yaml: the draft goes to a separate review path a
# human inspects and curates. Re-runnable whenever the real CV changes; its counts
# and names feed docs/probes/2026-09-21-cv-tex-spike.md.
#
# Usage:
#   bash scripts/cv-tex-spike.sh [--dry-run] [SOURCE.tex] [DRAFT.yaml]
#
#   --dry-run   Print what would run without reading anything.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

DRY_RUN=0
SOURCE=""
DRAFT=""

usage() {
  sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

positionals=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "cv-tex-spike: unknown option: $arg" >&2; exit 2 ;;
    *)
      positionals=$((positionals + 1))
      if [ "$positionals" -eq 1 ]; then
        SOURCE="$arg"
      else
        DRAFT="$arg"
      fi
      ;;
  esac
done

SOURCE="${SOURCE:-$ROOT/cv/base.tex}"
# A SEPARATE review path, deliberately NOT cv/cv.yaml: the importer must never
# write over the machine-canonical document.
DRAFT="${DRAFT:-$ROOT/cv/cv.draft.yaml}"

if [ ! -x "$PYTHON" ]; then
  echo "cv-tex-spike: no interpreter at $PYTHON (set PYTHON=... or create .venv)" >&2
  echo "  A venv built for another platform cannot load its native extensions here;" >&2
  echo "  the interpreter must match the platform you run on (docs/probes/README.md)." >&2
  exit 2
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Preflight: fail fast with a DISTINCT exit code and the underlying import error,
# rather than running with a broken environment.
preflight_err="$(mktemp)"
if ! "$PYTHON" -c "import app.cv.import_tex" 2>"$preflight_err" >/dev/null; then
  echo "cv-tex-spike: the interpreter cannot import the importer - $PYTHON" >&2
  cat "$preflight_err" >&2
  rm -f "$preflight_err"
  exit 2
fi
rm -f "$preflight_err"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "cv-tex-spike: dry run - nothing was read."
  echo "  interpreter: $PYTHON"
  echo "  source:      $SOURCE"
  echo "  draft:       $DRAFT"
  echo "would parse the source and write the review draft to the draft path."
  exit 0
fi

if [ ! -f "$SOURCE" ]; then
  echo "cv-tex-spike: no document at $SOURCE" >&2
  echo "  place the real document there first: mkdir -p cv artifacts" >&2
  exit 3
fi

"$PYTHON" -c "import pathlib,sys; from app.cv.import_tex import parse_tex, write_draft; source=pathlib.Path(sys.argv[1]); dest=pathlib.Path(sys.argv[2]); draft,report=parse_tex(source.read_text(encoding='utf-8')); write_draft(draft,dest); print(report.summary()); print('draft written to:', dest)" "$SOURCE" "$DRAFT"
