#!/usr/bin/env bash
# Assemble paper-access-overleaf.zip for Overleaf upload.
# Requires paper-access-overleaf-full.zip at repo root (IEEE Author Center kit
# with fonts + logo PNGs). Overwrites repo-root paper-access-overleaf.zip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KIT_ZIP="$ROOT/paper-access-overleaf-full.zip"
OUT_ZIP="$ROOT/paper-access-overleaf.zip"
PAPER_DIR="$ROOT/paper/ieee-paper"
STAGE="$(mktemp -d)"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

if [[ ! -f "$KIT_ZIP" ]]; then
  echo "error: missing $KIT_ZIP (IEEE Access Author Center kit archive)" >&2
  exit 1
fi

# Full kit at zip root (cls, fonts, logos) — drop prior compile artifacts only.
unzip -qo "$KIT_ZIP" -d "$STAGE"
rm -f "$STAGE"/paper-access.{aux,log,out,pdf} "$STAGE"/missfont.log 2>/dev/null || true

# Current paper + figures (pre-rendered concept PDFs required for Access).
cp "$PAPER_DIR/paper-access.tex" "$STAGE/"
mkdir -p "$STAGE/figures/pipeline_examples" "$STAGE/figures/authors"
cp "$PAPER_DIR/figures/"*.pdf "$STAGE/figures/"
cp "$PAPER_DIR/figures/pipeline_examples/"*.png "$STAGE/figures/pipeline_examples/"
cp "$PAPER_DIR/figures/authors/"*.jpg "$STAGE/figures/authors/"

for asset in logo.png notaglinelogo.png bullet.png ieeeaccess.cls spotcolor.sty; do
  if [[ ! -f "$STAGE/$asset" ]]; then
    echo "error: kit zip missing $asset" >&2
    exit 1
  fi
done

rm -f "$OUT_ZIP"
(
  cd "$STAGE"
  zip -rq "$OUT_ZIP" . -x "*.aux" -x "*.log" -x "*.out"
)

echo "wrote $OUT_ZIP ($(du -h "$OUT_ZIP" | cut -f1))"
unzip -l "$OUT_ZIP" | rg "logo|notag|bullet|paper-access.tex" || true
