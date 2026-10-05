#!/usr/bin/env bash
# Rebuild the full resubmission package into review_artifacts/submission/:
#   Access-2026-33821_revised_manuscript_clean.pdf        (paper-access.tex, IEEE Access kit)
#   Access-2026-33821_revised_manuscript_highlighted.pdf  (word-level highlights vs the portal-submitted manuscript)
#   Access-2026-33821_revised_highlight_change_index.pdf
#   Access-2026-33821_revised_response_to_reviewers.pdf
#   Access-2026-33821_revised_latex_source.zip
# Also rebuilds paper-build.pdf (IEEEtran). Needs pdflatex, git, uv.
set -euo pipefail
PAPER="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$PAPER/../.." && pwd)"
SUB="$PAPER/review_artifacts/submission"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
kit_build() {  # $1 = dir with paper-access.tex + kit files
  (cd "$1" && rm -f paper-access.aux && for _ in 1 2; do
     TEXFONTS=.: TFMFONTS=.: T1FONTS=.: TEXINPUTS=.: timeout 180 pdflatex -interaction=batchmode paper-access.tex >/dev/null 2>&1 || true
   done; grep -q "Output written" paper-access.log || { echo "Access build failed in $1" >&2; exit 1; })
}

# 1. IEEEtran twin
(cd "$PAPER" && for _ in 1 2; do pdflatex -interaction=batchmode paper-build.tex >/dev/null 2>&1 || true; done)

# 2. Access build from the Overleaf zip
bash "$PAPER/build-overleaf-zip.sh" >/dev/null
mkdir "$TMP/new" && (cd "$TMP/new" && unzip -q "$ROOT/paper-access-overleaf.zip")
kit_build "$TMP/new"
if grep -q "undefined" "$TMP/new/paper-access.log"; then echo "WARNING: undefined references" >&2; fi
cp "$TMP/new/paper-access.pdf" "$PAPER/paper-access.pdf"

# 3. Baseline: the manuscript as submitted through the portal (source zip downloaded from it)
B="$TMP/base"; mkdir "$B" && (cd "$B" && unzip -q "$PAPER/review_artifacts/baseline/submitted_manuscript_portal.zip")
kit_build "$B"

# 4. Highlighted PDF
mkdir -p "$PAPER/output/pdf" "$ROOT/output/baseline/snapshot/paper/ieee-paper"
cp "$TMP/new/paper-access.pdf" "$TMP/new/paper-access.aux" "$PAPER/output/pdf/"
cp "$B/paper-access.pdf" "$ROOT/output/baseline/snapshot/paper/ieee-paper/paper-access.pdf"
(cd "$ROOT" && uv run -q --with pymupdf --with reportlab python "$PAPER/build-highlighted.py")

# 5. Response PDF
(cd "$PAPER" && uv run -q --with markdown --with weasyprint python build-response-pdf.py)

# 6. Package
mkdir -p "$SUB"
cp "$PAPER/output/pdf/paper-access.pdf" "$SUB/Access-2026-33821_revised_manuscript_clean.pdf"
cp "$PAPER/output/pdf/paper-access-highlighted.pdf" "$SUB/Access-2026-33821_revised_manuscript_highlighted.pdf"
cp "$PAPER/output/pdf/highlight-change-index.pdf" "$SUB/Access-2026-33821_revised_highlight_change_index.pdf"
cp "$PAPER/review_artifacts/RESPONSE_TO_REVIEWERS.pdf" "$SUB/Access-2026-33821_revised_response_to_reviewers.pdf"
cp "$ROOT/paper-access-overleaf.zip" "$SUB/Access-2026-33821_revised_latex_source.zip"
echo "pages: access $(pdfinfo "$SUB/Access-2026-33821_revised_manuscript_clean.pdf" | awk '/Pages/{print $2}'), build $(pdfinfo "$PAPER/paper-build.pdf" | awk '/Pages/{print $2}'), response $(pdfinfo "$SUB/Access-2026-33821_revised_response_to_reviewers.pdf" | awk '/Pages/{print $2}')"
grep -c "PENDING" "$PAPER/paper-access.tex" "$PAPER/review_artifacts/RESPONSE_TO_REVIEWERS.md" || true
