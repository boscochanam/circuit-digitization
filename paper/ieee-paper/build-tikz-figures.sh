#!/usr/bin/env bash
# Pre-render native TikZ concept figures to PDF for paper-access.tex.
# ieeeaccess.cls spot colors conflict with tikz's \\shipout hook; Access builds
# must includegraphics these PDFs instead of \\input{*_tikz.tex}.
set -euo pipefail
cd "$(dirname "$0")/figures"

build_one() {
  local stem=$1
  local standalone="${stem}_standalone.tex"
  local out="${stem}.pdf"
  cat >"$standalone" <<EOF
\\documentclass[tikz,border=3pt]{standalone}
\\usepackage{tikz}
\\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc}
\\begin{document}
\\input{${stem}_tikz.tex}
\\end{document}
EOF
  pdflatex -interaction=nonstopmode -halt-on-error "$standalone" >/dev/null
  mv -f "${stem}_standalone.pdf" "$out"
  rm -f "${stem}_standalone.aux" "${stem}_standalone.log" "$standalone"
  echo "wrote figures/$out"
}

build_one pipeline_overview
build_one endpoint_graph
build_one completion
