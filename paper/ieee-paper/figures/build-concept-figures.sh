#!/usr/bin/env sh
# Regenerate the standalone PDF versions of the native-TikZ concept figures.
#
# paper-access.tex (IEEE Access, ieeeaccess.cls) cannot use inline TikZ: the
# class + spotcolor.sty conflict with PGF and break the compile (lost title,
# inflated page count). So paper-access.tex \includegraphics these PDFs instead.
# paper-build.tex (IEEEtran) still \inputs the *_tikz.tex sources directly.
#
# Edit a *_tikz.tex source, then run this to refresh the PDF. Needs pdflatex +
# the standalone class.
set -e
cd "$(dirname "$0")"
for fig in pipeline_overview endpoint_graph completion; do
  cat > _sa.tex <<EOF
\documentclass[border=3pt]{standalone}
\usepackage{mathptmx}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc}
\usepackage{xcolor}
\begin{document}
\input{${fig}_tikz.tex}
\end{document}
EOF
  pdflatex -interaction=nonstopmode _sa.tex >/dev/null
  mv -f _sa.pdf "${fig}.pdf"
  echo "regenerated ${fig}.pdf"
done
rm -f _sa.tex _sa.aux _sa.log
