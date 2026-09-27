from pathlib import Path
import difflib
import unicodedata
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'output/baseline/snapshot/paper/ieee-paper/paper-access.pdf'
NEW = ROOT / 'paper/ieee-paper/output/pdf/paper-access.pdf'
HIGHLIGHTED = ROOT / 'paper/ieee-paper/output/pdf/paper-access-highlighted.pdf'
OUT = ROOT / 'paper/ieee-paper/review_artifacts/OLD_NEW_ANNOTATED_DRAFT.pdf'
old, new, highlighted = fitz.open(OLD), fitz.open(NEW), fitz.open(HIGHLIGHTED)
assert len(old) == 11 and len(new) == len(highlighted) == 12
assert all(new[i].get_text() == highlighted[i].get_text() for i in range(len(new)))
result = fitz.open()
INK=(.063,.094,.157); MUTED=(.4,.44,.51); BLUE=(.09,.36,.83)
GREEN=(.10,.44,.30); AMBER=(.54,.35,0); RULE=(.81,.84,.87)
PAPER = fitz.Rect(16, 47, 592, 830)
SIDE_X, SIDE_W = 606, 178
notes = {
 1: ('Title, abstract, and claim boundary', ['Structural-netlist title replaces SPICE-ready wording.', 'OPEN: author approval, byline, funding, ORCIDs and response signatory.', 'Git author on manuscript revisions: Bosco Chanam; individual contribution credit requires confirmation.']),
 2: ('Pipeline and figures', ['Pipeline output now says structural netlist; released checkpoint is labeled 89.0%.', 'OPEN: graphical abstract exceeds the stated size limit.', 'Check that every consumed figure is current.']),
 3: ('Related work and framing', ['Review suggested references and the scope of comparisons.', 'OPEN: old page number and new page number are not line-aligned.']),
 4: ('Method and endpoint graph', ['Methods and implemented pin/join rules have been reconciled.', 'OPEN: device-specific pin behavior is not fully validated.']),
 5: ('Wire benchmark and examples', ['134-image result reproduced on 704x704 identity copies.', 'OPEN: full-resolution original scans were not evaluated; label coordinate transfer is not established.']),
 6: ('Wire and synthetic tables', ['36-config ranking and a16 replay match saved artifacts.', 'OPEN: older Pranavesh-era threshold/table rows do not all reproduce; do not silently restate them.']),
 7: ('Synthetic and real-image results', ['31-image join replay matches saved per-image counts.', 'OPEN: results use annotated component boxes, not autonomous image-to-netlist correctness.']),
 8: ('Ablations and uncertainty', ['Response adds bounded mechanism/edge ablations.', 'OPEN: crossover detector claims need raw per-instance evidence or narrower wording.']),
 9: ('Drafter and generalization limits', ['Within-corpus subgroup mapping is documented.', 'OPEN: unknown detector train/test overlap; 34 annotated to 31 scored needs author sign-off.']),
 10: ('Discussion and limitations', ['Best-checkpoint metric distinguished from final epoch.', 'OPEN: no extreme-size or controlled mixed-size experiment; no simulation-equivalence proof.']),
 11: ('Capabilities and references', ['Export, OCR/value and device limitations are separated.', 'OPEN: human review of reviewer response and final bibliography.']),
 12: ('Additional new page', ['There is no corresponding old manuscript page 12.', 'OPEN: verify updated clean/highlighted PDFs, archive, release hashes and final author approval.']),
}

# Provisional page-level triage, not an approval of the paper or a person-by-person credit.
reviews = {
 1: ('OPEN PROBLEM', 'Author and response sign-off remain pending.', 'Confirm byline, funding, ORCIDs, response signatory and the exact baseline with the authors.'),
 2: ('OPEN PROBLEM', 'Graphical abstract was 60,323 bytes against a stated 45 KB cap; final asset status not verified.', 'Compress/rebuild it below the limit, then inspect the actual uploaded figure and PDF.'),
 3: ('NO PAGE-SPECIFIC PROBLEM FOUND', 'No concrete defect established on this page in this review; that is not overall approval.', 'Authors should check the cited works and page-shifted wording against the old source.'),
 4: ('LIMITATION / CHECK', 'Device-specific pins are not fully validated.', 'Keep generic geometry distinct from verified device behavior; check the response wording.'),
 5: ('OPEN EVIDENCE GAP', 'Wire rerun used 704x704 identity copies, not full-resolution CGHD scans.', 'Name the preprocessed image domain; do not claim original-resolution performance.'),
 6: ('OPEN HISTORICAL DISCREPANCY', 'Some older Pranavesh-era threshold/topology rows did not reproduce exactly.', 'Do not reuse old numbers as current results; reconcile any that remain in active text.'),
 7: ('NO RERUN MISMATCH FOUND', 'The 31-image annotated-box join output matched saved per-image counts; autonomous accuracy was not shown.', 'Retain the annotated-box caveat and avoid end-to-end claims.'),
 8: ('OPEN EVIDENCE GAP', 'Crossover detector localization lacks a committed per-instance output record.', 'Add inputs, matching rule and per-instance output, or narrow the specific numerical claim.'),
 9: ('OPEN AUTHOR CHECK', '34-to-31 exclusions await author sign-off; detector training overlap with scored images is unknown.', 'Confirm exclusions from source records; avoid any held-out claim without a split manifest.'),
 10: ('LIMITATIONS DISCLOSED', 'Extreme-size, mixed-size and simulation-equivalence claims are not experimentally established.', 'Keep them explicit limitations; do not convert them into demonstrated robustness.'),
 11: ('NEEDS AUTHOR CHECK', 'Response and bibliography still require human review.', 'Validate references, author details and response-to-reviewers before submission.'),
 12: ('OPEN RELEASE CHECK', 'The extra page has no old counterpart; the changed submission package is not finally certified.', 'Verify clean/highlighted parity, ZIP, hashes, figure size and approval before upload.'),
}

def source_words(doc):
    out=[]
    for page_no, page in enumerate(doc):
        for word in page.get_text('words', sort=False):
            if word[1] < 45 or word[3] > page.rect.height - 35:
                continue
            token=unicodedata.normalize('NFKC',word[4]).replace('\u00ad','')
            out.append((token,page_no,fitz.Rect(word[:4])))
    return out

old_words, new_words = source_words(old), source_words(new)
old_marks = [[] for _ in old]
changes = difflib.SequenceMatcher(None,
    [w[0] for w in old_words], [w[0] for w in new_words],
    autojunk=False).get_opcodes()
for kind, i1, i2, j1, j2 in changes:
    if kind == 'equal':
        continue
    for _,page_no,rect in old_words[i1:i2]:
        old_marks[page_no].append(rect)


def draw_text_marks(target, source, rects, color):
    scale=min(PAPER.width/source.rect.width,PAPER.height/source.rect.height)
    x0=PAPER.x0+(PAPER.width-source.rect.width*scale)/2
    y0=PAPER.y0+(PAPER.height-source.rect.height*scale)/2
    for r in rects:
        box=fitz.Rect(x0+r.x0*scale,y0+r.y0*scale,
                      x0+r.x1*scale,y0+r.y1*scale)
        target.draw_rect(box,color=None,fill=color,fill_opacity=.27,overlay=True)


def new_text_marks(source):
    rects=[]
    for annot in source.annots() or []:
        if annot.type[0] != 8 or not annot.vertices:
            continue
        for i in range(0,len(annot.vertices),4):
            verts=annot.vertices[i:i+4]
            if len(verts)==4:
                xs=[v[0] for v in verts]; ys=[v[1] for v in verts]
                rects.append(fitz.Rect(min(xs),min(ys),max(xs),max(ys)))
    return rects


def line(page, text, x, y, size=9, color=INK, font='helv', max_width=SIDE_W):
    # Wrap by measured font width rather than assuming a fixed character count.
    words=text.split(); parts=[]; cur=''
    for word in words:
        candidate=(cur+' '+word).strip()
        if fitz.get_text_length(candidate,fontname=font,fontsize=size) <= max_width:
            cur=candidate
        else:
            if cur: parts.append(cur)
            cur=word
    if cur: parts.append(cur)
    for part in parts:
        page.insert_text((x,y),part,fontsize=size,fontname=font,color=color)
        y += size*1.42
    return y

def card(page, title, bullets, start):
    y=line(page,title,SIDE_X,start,size=10.2,color=INK,font='hebo')+8
    for s in bullets:
        color=AMBER if s.startswith('OPEN:') else MUTED
        y=line(page,s,SIDE_X,y,size=8.4,color=color,max_width=SIDE_W-3)+7
    return y

def review_block(page, pair, start):
    status, problem, action=reviews[pair]
    y=start+5
    page.draw_line((SIDE_X,y),(784,y),color=RULE,width=.7)
    y+=17
    y=line(page,'PROBLEMS / NO PROBLEMS',SIDE_X,y,size=8.6,color=BLUE,font='hebo')+2
    status_color=GREEN if status.startswith('NO ') else AMBER
    y=line(page,status,SIDE_X,y,size=8.3,color=status_color,font='hebo')+5
    y=line(page,problem,SIDE_X,y,size=8.0,color=MUTED)+9
    y=line(page,'SUGGESTED ACTION',SIDE_X,y,size=8.6,color=BLUE,font='hebo')+2
    y=line(page,action,SIDE_X,y,size=8.0,color=MUTED)+4
    return y

def field(page, name, rect, multiline=False):
    w=fitz.Widget()
    w.field_name=name
    w.field_label=name.replace('_',' ')
    w.field_type=fitz.PDF_WIDGET_TYPE_TEXT
    w.field_value=''
    w.rect=rect
    w.text_font='Helv'
    w.text_fontsize=9
    w.text_color=INK
    w.border_color=RULE
    w.fill_color=(.975,.984,1)
    w.border_width=.8
    if multiline:
        w.field_flags=fitz.PDF_TX_FIELD_IS_MULTILINE
    page.add_widget(w)

for idx in range(len(new)):
    pair=idx+1
    for is_new in (False,True):
        p=result.new_page(width=800,height=860)
        p.draw_rect(p.rect,color=None,fill=(1,1,1))
        tag='NEW / CURRENT DRAFT' if is_new else 'OLD / REVIEW BASELINE'
        tag_color=GREEN if is_new else BLUE
        p.insert_text((16,30),f'{tag}  |  manuscript page {pair}',fontsize=13,fontname='hebo',color=tag_color)
        p.insert_text((SIDE_X,30),f'PDF page {len(result)}',fontsize=9,fontname='hebo',color=MUTED)
        p.draw_line((16,38),(784,38),color=RULE,width=.7)
        if is_new:
            p.show_pdf_page(PAPER,new,idx,keep_proportion=True)
            draw_text_marks(p,new[idx],new_text_marks(highlighted[idx]),(1,.78,.08))
        elif idx < len(old):
            p.show_pdf_page(PAPER,old,idx,keep_proportion=True)
            draw_text_marks(p,old[idx],old_marks[idx],(1,.55,.60))
        else:
            p.draw_rect(PAPER,color=RULE,fill=(.975,.984,1))
            p.insert_text((100,395),'No matching old page 12',fontsize=20,fontname='hebo',color=MUTED)
            p.insert_text((100,422),'The revised manuscript gained an additional page.',fontsize=11,color=MUTED)
        p.draw_line((599,47),(599,831),color=RULE,width=.7)
        if is_new:
            p.insert_text((SIDE_X,55),'GOLD = added / revised text',fontsize=8.4,fontname='hebo',color=AMBER)
            title,bullets=notes[pair]
            y=review_block(p,pair,card(p,title,bullets,82)+4)
            assert y < 515, (pair,y)
            y=max(y+18,450)
            p.draw_line((SIDE_X,y-12),(784,y-12),color=RULE,width=.7)
            p.insert_text((SIDE_X,y),'YOUR REVIEW STATUS',fontsize=8.6,fontname='hebo',color=BLUE)
            field(p,f'pair_{pair:02d}_review_status',fitz.Rect(SIDE_X,y+8,784,y+33))
            y+=47
            p.insert_text((SIDE_X,y),'CHANGE OWNER / CONTRIBUTOR',fontsize=8.6,fontname='hebo',color=BLUE)
            field(p,f'pair_{pair:02d}_contributor',fitz.Rect(SIDE_X,y+8,784,y+36))
            y+=51
            p.insert_text((SIDE_X,y),'COMMENTS / DECISION',fontsize=8.6,fontname='hebo',color=BLUE)
            field(p,f'pair_{pair:02d}_comments',fitz.Rect(SIDE_X,y+8,784,783),multiline=True)
            p.insert_text((SIDE_X,802),'Editable fields + printable space',fontsize=7.6,color=MUTED)
        else:
            p.insert_text((SIDE_X,55),'ROSE = removed / replaced text',fontsize=8.4,fontname='hebo',color=(.68,.24,.34))
            y=card(p,'How to use this pair',[
                'This OLD page is followed by its NEW page.',
                'Pairing is by PDF page index, not exact text or section alignment.',
                'Baseline: pre-August-13 Git snapshot 33f5e3d; not independently portal-confirmed.',
                'Write the contributor and decision on the following NEW page.'
            ],82)
            y=review_block(p,pair,y+8)
            y=max(y+22,490)
            p.draw_line((SIDE_X,y-14),(784,y-14),color=RULE,width=.7)
            line(p,'Attribution note: Pranavesh authored earlier benchmark commits. Git lists Bosco Chanam as author of the later manuscript revision commits; confirm individual edit credit with the authors.',SIDE_X,y,size=8.2,color=AMBER)
        p.insert_text((16,848),'Internal coauthor review only - not the IEEE submission manuscript.',fontsize=8,color=MUTED)
result.set_metadata({'title':'IEEE Access 33821 - interleaved old/new coauthor review draft',
                     'author':'Clawsco for Bosco Chanam',
                     'subject':'Old pages odd, new pages even; editable attribution and comment fields; not portal-confirmed baseline'})
OUT.parent.mkdir(parents=True,exist_ok=True)
result.save(OUT,garbage=4,deflate=True)
print(f'{OUT} pages={len(result)} old={len(old)} new={len(new)} fields={3*len(new)}')
