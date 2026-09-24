"""Render review documents and audit the local manuscript package; no experiments run."""
from pathlib import Path
import collections
import difflib
import hashlib
import html
import json
import re
import subprocess

import pymupdf as fitz
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfgen import canvas

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent.parent
OUT = PAPER / 'output/pdf'
REVIEW = PAPER / 'review_artifacts'
BASE = '4d636d0'
OUT.mkdir(parents=True, exist_ok=True)
for name, filename in [('Review','segoeui.ttf'),('Review-Bold','segoeuib.ttf'),('Review-Italic','segoeuii.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / filename)))
pdfmetrics.registerFontFamily('Review', normal='Review', bold='Review-Bold', italic='Review-Italic')
styles = getSampleStyleSheet()
for style in styles.byName.values():
    style.fontName = 'Review'
    style.wordWrap = 'LTR'
styles['BodyText'].fontSize = 9
styles['BodyText'].leading = 13
styles['BodyText'].spaceAfter = 7
styles['Heading1'].fontName = styles['Heading2'].fontName = 'Review-Bold'

def markup(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    return text.replace('`', '')

def para(text, style='BodyText'):
    return Paragraph(markup(text), styles[style])

def footer(c, doc):
    c.setFont('Review', 8)
    c.drawString(42, 24, 'Access-2026-33821 | Local revision package | 24 September 2026')
    c.drawRightString(570, 24, str(doc.page))

def document(path, story):
    SimpleDocTemplate(str(path), pagesize=(612,792), leftMargin=42, rightMargin=42,
                      topMargin=40, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)

access = fitz.open(OUT / 'paper-access.pdf')
def normalized(text):
    return re.sub(r'\s+', ' ', re.sub(r'-\s*\n\s*', '', text)).lower()
page_text = [normalized(p.get_text()) for p in access]
def pages_for(needles):
    return sorted({i+1 for i,t in enumerate(page_text) for n in needles if n.lower() in t})
anchors = {
    'R1-1':['Thirty-four images','drafter identities'],
    'R1-2':['Connectivity evaluation, generic pin'],
    'R1-3':['The tolerances are manually','bounded within-benchmark reach'],
    'R1-4':['illustrative SPICE export','External values'],
    'R1-5':['Complexity of the 31-image'],
    'R1-6':['fear generalization','neighboring hardware'],
    'R2-1':['A proposed expansion protocol','confidence intervals'],
    'R2-2':['The paired VLM-minus-join'],
    'R2-3':['We present structural'],
    'R2-4':['Detector-miss effects were not measured'],
    'R2-5':['Leave-one-out ablation','Full occlusion removal'],
    'R2-6':['intra-image size variance','completion retains this scale'],
}
page_map = {key:pages_for(phrases) for key,phrases in anchors.items()}
aux = (OUT/'paper-access.aux').read_text()
for key, label in [('R1-1','sec:real_eval'),('R1-3','sec:real_eval'),('R2-1','sec:limitations')]:
    match = re.search(r'\\newlabel\{'+re.escape(label)+r'\}\{\{.*?\}\{(\d+)\}',aux)
    assert match, label
    page_map[key] = sorted(set(page_map[key]+[int(match[1])]))
page_map['R2-3'] = sorted(set([1,2]+page_map['R2-3']))
assert all(page_map.values()), page_map
(OUT / 'response_page_map.json').write_text(json.dumps(page_map, indent=2))
response = (REVIEW / 'RESPONSE_TO_REVIEWERS.md').read_text(encoding='utf-8')
sections = re.split(r'(?=### Reviewer#)', response)[1:]
assert len(sections) == 12
story = [para('Response to Reviewers','Title'), para('Original Manuscript ID: Access-2026-33821'),
         para('Revised title: From Hand-Drawn Schematics to Structural Circuit Netlists: A Deterministic Pipeline with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark'),
         para('For coauthor review. Page references refer to the accompanying locally rebuilt IEEE Access manuscript. The highlighted comparison uses commit 33f5e3d, selected by the author as the latest manuscript before August 13. Final submission approval remains pending.')]
for section in sections:
    m = re.match(r'### Reviewer#(\d), Concern # (\d): (.*)', section)
    key = f'R{m[1]}-{m[2]}'
    section_story = [para(f'{key}: {m[3]}','Heading2')]
    for block in section.split('\n\n')[1:]:
        if block.strip().startswith('**'):
            section_story.append(para(block.strip()))
    section_story.append(para('Manuscript locations: pp. '+', '.join(map(str,page_map[key]))+'.'))
    from reportlab.platypus import KeepTogether
    story.append(KeepTogether(section_story))
document(OUT / 'response-to-reviewers.pdf', story)

status = (REVIEW / 'REVIEWER_STATUS_REPORT.md').read_text(encoding='utf-8')
rows = [line.strip('|').split('|') for line in status.splitlines() if re.match(r'\| R[12]-',line)]
assert len(rows)==12
story = [para('Reviewer Status Report','Title'), para('Updated local build, 24 September 2026. Scientific limitations remain distinct from source verification. Portal confirmation of the author-selected baseline, author metadata reconciliation and package approval are pending.')]
for row in rows:
    story.append(para(row[0].strip(),'Heading2'))
    for label,content in zip(['Reviewer concern','Action taken','Remaining'],row[1:]):
        story.append(para('**'+label+':** '+content.strip()))
document(OUT / 'reviewer-status-report.pdf', story)

# A new vector graphical abstract, derived from the current pipeline and scoped claims.
ga = OUT / 'graphical-abstract.pdf'
c = canvas.Canvas(str(ga), pagesize=(1000,420))
c.setFillColor(colors.HexColor('#F4F7F9')); c.rect(0,0,1000,420,fill=1,stroke=0)
c.setFillColor(colors.HexColor('#006B91')); c.setFont('Review-Bold',25)
c.drawString(32,376,'Hand-drawn schematics to structural circuit netlists')
c.setFont('Review',13); c.drawString(32,348,'Deterministic wire extraction, endpoint-graph joining, and degree-budget completion')
labels=[('Input image','Scanned schematic'),('Component detection','Oriented boxes'),('Occlusion','Local median fill'),('Wire extraction','Sauvola + CCL + PCA'),('Wire joining','Graph + completion'),('Structural netlist','Inferred pin-to-node map')]
for i,(title,detail) in enumerate(labels):
    x=32+i*159
    c.setFillColor(colors.HexColor('#DDECF2' if i not in (3,4) else '#D6EAD9'))
    c.roundRect(x,210,145,88,8,fill=1,stroke=0)
    c.setFillColor(colors.HexColor('#183341')); c.setFont('Review-Bold',11); c.drawCentredString(x+72.5,261,title)
    c.setFont('Review',9); c.drawCentredString(x+72.5,238,detail)
    if i<5:
        c.setStrokeColor(colors.HexColor('#183341')); c.line(x+147,254,x+157,254)
        c.line(x+153,258,x+157,254); c.line(x+153,250,x+157,254)
c.setFont('Review-Bold',16); c.drawString(32,169,'31 human-verified images | component-pair micro-F1: 0.890')
c.setFont('Review',12)
for y,line in [(142,'Joining evaluation uses annotated component boxes and detected wires from one corpus (CGHD-1152).'),
               (101,'Component-pair F1 does not certify pin identities, exact nets, absence of shorts, or simulation equivalence.'),
               (75,'Component values and device models require external specification; real-scan simulation is unvalidated.')]:
    c.drawString(32,y,line)
c.save()
gadoc=fitz.open(ga)
gadoc[0].get_pixmap(matrix=fitz.Matrix(2,2)).save(str(PAPER/'figures/graphical_abstract.jpg'))

diff = subprocess.check_output(['git','diff',BASE,'--','paper/ieee-paper/paper-access.tex',
    'paper/ieee-paper/paper-build.tex','paper/ieee-paper/review_artifacts/RESPONSE_TO_REVIEWERS.md'],cwd=ROOT,text=True)
(OUT/'changes-since-4d636d0.diff').write_text(diff,encoding='utf-8')
story=[para('Revision Change Record','Title'),para('Comparison baseline: upstream commit 4d636d0, 17 September 2026. This is a local-edit record, not the highlighted comparison against the originally reviewed submission.')]
for line in diff.splitlines():
    if line.startswith(('+++','---','@@','diff ')):
        story.append(para(line,'Heading3'))
    elif line.startswith(('+','-')):
        story.append(para(('AFTER: ' if line.startswith('+') else 'BEFORE: ')+line[1:]))
document(OUT/'changes-since-4d636d0.pdf',story)

# Inspect every produced PDF page for text outside the media box and render contact sheets.
from PIL import Image, ImageOps, ImageDraw
checks=[]
for pdf in sorted(OUT.glob('*.pdf')):
    doc=fitz.open(pdf)
    thumbs=[]
    for i,page in enumerate(doc):
        bad=[b[:4] for b in page.get_text('blocks') if b[6]==0 and not (page.rect+(-1,-1,1,1)).contains(fitz.Rect(b[:4]))]
        checks.append({'file':pdf.name,'page':i+1,'out_of_page_text_blocks':len(bad)})
        pix=page.get_pixmap(matrix=fitz.Matrix(.65,.65))
        im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        im.thumbnail((400,540))
        tile=Image.new('RGB',(420,570),'#ddd'); tile.paste(im,(10,20))
        ImageDraw.Draw(tile).text((10,552),f'{pdf.name} p{i+1}',fill='black')
        thumbs.append(tile)
    for start in range(0,len(thumbs),6):
        sheet=Image.new('RGB',(1260,1140),'white')
        for j,im in enumerate(thumbs[start:start+6]): sheet.paste(im,((j%3)*420,(j//3)*570))
        sheet.save(OUT/f'{pdf.stem}-contact-{start//6+1}.png')
(OUT/'page-checks.json').write_text(json.dumps(checks,indent=2))
print(json.dumps({'pages':len(access),'page_map':page_map,'out_of_page_blocks':sum(c['out_of_page_text_blocks'] for c in checks)},indent=2))
