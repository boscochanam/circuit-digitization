#!/usr/bin/env python3
"""Render REVIEWER_STATUS_REPORT.md -> REVIEWER_STATUS_REPORT.pdf.

The Markdown carries inline HTML spans (st-ok / st-warn / st-block) that the
original WeasyPrint build styled. No generator was ever committed, so this
recreates one: Markdown tables + inline HTML -> styled HTML -> WeasyPrint.

Run:  python3.12 paper/ieee-paper/build-status-report.py
"""
from pathlib import Path
import markdown
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
ART = HERE / "review_artifacts"
SRC = ART / "REVIEWER_STATUS_REPORT.md"
OUT = ART / "REVIEWER_STATUS_REPORT.pdf"

CSS = """
@page { size: A4 landscape; margin: 14mm 12mm;
        @bottom-center { content: counter(page) " / " counter(pages);
                         font-size: 8pt; color: #666; } }
body { font-family: "DejaVu Sans", sans-serif; font-size: 7.6pt; line-height: 1.35; color: #111; }
h1 { font-size: 15pt; } h2 { font-size: 11pt; margin-top: 10px; }
p, li { font-size: 7.9pt; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; }
th, td { border: 0.5pt solid #bbb; padding: 3px 4px; vertical-align: top;
         word-wrap: break-word; overflow-wrap: anywhere; }
th { background: #eee; font-size: 8pt; }
td:nth-child(1) { width: 11%; font-weight: bold; }
td:nth-child(2) { width: 40%; }
td:nth-child(3) { width: 40%; }
td:nth-child(4) { width: 9%; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 7pt;
       background: #f3f3f3; padding: 0 2px; }
blockquote { margin: 4px 0 8px 0; padding-left: 8px; border-left: 2pt solid #ccc; color: #333; }
.st-ok    { color: #0a7a2f; font-weight: bold; }
.st-warn  { color: #a86400; font-weight: bold; }
.st-block { color: #b3261e; font-weight: bold; }
"""


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "sane_lists", "md_in_html"])
    html = f"<!doctype html><html><head><meta charset='utf-8'>" \
           f"<style>{CSS}</style></head><body>{body}</body></html>"
    HTML(string=html, base_url=str(ART)).write_pdf(str(OUT))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
