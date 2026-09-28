"""Highlight rendered changes against the July 2026 submitted manuscript (commit 33f5e3d).

Inputs: output/pdf/paper-access.pdf + .aux (current Access build) and
output/baseline/snapshot/paper/ieee-paper/paper-access.pdf (33f5e3d built with the same kit)."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import subprocess
import unicodedata
import pymupdf as fitz
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from xml.sax.saxutils import escape

PAPER=Path(__file__).resolve().parent
ROOT=PAPER.parent.parent
OUT=PAPER/'output/pdf'
BASE='33f5e3d37a85641b13bffaf7fc34b94eb5d35c47'
baseline=ROOT/'output/baseline/snapshot/paper/ieee-paper/paper-access.pdf'
old=fitz.open(baseline)
new=fitz.open(OUT/'paper-access.pdf')

def words(doc):
    result=[]
    for pno,p in enumerate(doc):
        for w in p.get_text('words',sort=False):
            if w[1]<45 or w[3]>p.rect.height-35:
                continue
            text=unicodedata.normalize('NFKC',w[4]).replace('\u00ad','')
            result.append((text,pno,w[:4]))
    return result

a,b=words(old),words(new)
ops=difflib.SequenceMatcher(None,[w[0] for w in a],[w[0] for w in b],autojunk=False).get_opcodes()
records=[]
for tag,i1,i2,j1,j2 in ops:
    if tag=='equal': continue
    groups={}
    for _,pno,rect in b[j1:j2]: groups.setdefault(pno,[]).append(fitz.Rect(rect).quad)
    for pno,quads in groups.items():
        page=new[pno]
        annot=page.add_highlight_annot(quads)
        annot.set_info(title='Revision against 33f5e3d',content=f'Text change {len(records)+1}: {tag}')
        annot.update()
    records.append({'id':len(records)+1,'kind':tag,'baseline_pages':sorted({w[1]+1 for w in a[i1:i2]}),
                    'revised_pages':sorted({w[1]+1 for w in b[j1:j2]}),
                    'before':' '.join(w[0] for w in a[i1:i2]),'after':' '.join(w[0] for w in b[j1:j2])})

# Changed figure PDFs/images need explicit marking even when embedded text is unchanged.
figures={
 'pipeline_overview.pdf':'fig:pipeline',
 'endpoint_graph.pdf':'fig:endpoint_graph',
 'completion.pdf':'fig:completion',
 'wire_benchmark.pdf':'fig:wire_benchmark',
 'real_join_comparison.pdf':'fig:real_join_fig',
 'rescale_robustness.pdf':'fig:rescale',
 'join_comparison.pdf':'fig:join_comparison',
 'pipeline_examples/C37-D2-P4-jpg.png':'fig:pipeline_examples',
 'pipeline_examples/C111-D1-P1-jpg.png':'fig:pipeline_examples',
}
aux=(OUT/'paper-access.aux').read_text()
figure_records=[]
for asset,label in figures.items():
    current=PAPER/'figures'/asset
    try:
        previous=subprocess.check_output(['git','show',f'{BASE}:paper/ieee-paper/figures/{asset}'],cwd=ROOT,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError: previous=b''
    if previous==current.read_bytes(): continue
    match=re.search(r'\\newlabel\{'+re.escape(label)+r'\}\{\{.*?\}\{(\d+)\}',aux)
    if not match: raise RuntimeError('Figure page missing: '+label)
    pno=int(match[1])-1
    figure_records.append({'asset':asset,'label':label,'revised_page':pno+1})

# Light page frames document figure/layout changes without covering the artwork.
for pno in sorted({r['revised_page']-1 for r in figure_records}):
    page=new[pno]
    annot=page.add_rect_annot(fitz.Rect(25,45,page.rect.width-25,page.rect.height-35))
    annot.set_colors(stroke=(1,.6,0))
    annot.set_border(width=1)
    annot.set_info(title='Figure / layout revision',content='Updated figure(s) on this page; see highlight-change-index.json for assets. Text highlights are separate.')
    annot.update()

new.set_metadata({**new.metadata,'subject':f'Changes against user-selected latest pre-August-13 revision {BASE}; not portal-confirmed.'})
new.save(OUT/'paper-access-highlighted.pdf',garbage=4,deflate=True)
assert [p.get_text() for p in new]==[p.get_text() for p in fitz.open(OUT/'paper-access.pdf')]
(OUT/'highlight-change-index.json').write_text(json.dumps({'baseline_commit':BASE,'selection':'Latest manuscript before Aug 13, per user instruction; not independently portal-confirmed.',
 'text_changes':records,'figure_changes':figure_records,'text_identical_to_clean':True},indent=2),encoding='utf-8')
diff=subprocess.check_output(['git','diff',BASE,'--','paper/ieee-paper/paper-access.tex','paper/ieee-paper/paper-build.tex'],cwd=ROOT,text=True)
(OUT/'reviewed-baseline-source.diff').write_text(diff,encoding='utf-8')

styles=getSampleStyleSheet()
styles['BodyText'].fontSize=9;styles['BodyText'].leading=12
story=[Paragraph('Highlighted Manuscript: Change and Deletion Index',styles['Title']),
 Paragraph('Baseline: '+BASE+'. Selected as the latest manuscript before August 13 under the author\'s instruction. Yellow marks show inserted/replaced rendered words; orange frames identify pages containing changed figure assets. The clean PDF text is unchanged by annotations. Source-only layout/preamble edits are preserved in reviewed-baseline-source.diff. This index records removed text that cannot be highlighted in the revised manuscript.',styles['BodyText'])]
for r in records:
    story.append(Paragraph(f"Change {r['id']}: {r['kind']} | old pp. {r['baseline_pages']} | new pp. {r['revised_pages']}",styles['Heading3']))
    for label,key in [('Before (including deletions)','before'),('After','after')]:
        text=r[key] or '(none)'
        story.append(Paragraph('<b>'+label+':</b> '+escape(text),styles['BodyText']))
SimpleDocTemplate(str(OUT/'highlight-change-index.pdf'),leftMargin=40,rightMargin=40,topMargin=40,bottomMargin=40).build(story)
print(f'Highlighted {len(records)} text changes and {len(figure_records)} changed figure assets; clean text equality PASS.')
