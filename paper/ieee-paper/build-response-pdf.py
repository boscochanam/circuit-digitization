from pathlib import Path
import markdown
from weasyprint import HTML
ART = Path("/home/claw/circuit-digitization/paper/ieee-paper/review_artifacts")
CSS = """
@page { size: A4; margin: 18mm 16mm; @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color:#666; } }
body { font-family:"DejaVu Sans",sans-serif; font-size:9.5pt; line-height:1.45; color:#111; }
h1 { font-size:15pt; border-bottom:1pt solid #999; padding-bottom:3px; }
h2 { font-size:12pt; margin-top:14px; color:#0b3d6b; border-bottom:0.5pt solid #ccc; }
h3 { font-size:10pt; margin-top:11px; }
code { font-family:"DejaVu Sans Mono",monospace; font-size:8.2pt; background:#f3f3f3; padding:0 2px; }
blockquote { border-left:2pt solid #bbb; margin:5px 0; padding-left:9px; color:#333; }
p { margin: 5px 0; }
"""
body = markdown.markdown((ART/"RESPONSE_TO_REVIEWERS.md").read_text(encoding="utf-8"),
                         extensions=["tables","sane_lists","md_in_html"])
HTML(string=f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>",
     base_url=str(ART)).write_pdf(str(ART/"RESPONSE_TO_REVIEWERS.pdf"))
print("wrote", ART/"RESPONSE_TO_REVIEWERS.pdf")
