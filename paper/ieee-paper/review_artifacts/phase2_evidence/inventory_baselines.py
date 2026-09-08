"""Read-only input inventory; writes reports here, never builds a manuscript."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent / 'baselines'
ROOT = Path('paper/ieee-paper')
V = Path('/home/claw/circuit-digitization-validation-20260907/context')
PARENT = '9bbe9e9'
CURRENT = '02da5e6'
manifest = {'current_source_commit': CURRENT, 'fork_parent': PARENT,
            'warning': 'Candidate inventory only. No determination of the source or PDF IEEE reviewed.',
            'files': {}, 'diffs': {}}

def record(name, origin, data):
    manifest['files'][name] = {'origin': origin, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return data.decode() if not name.endswith('pdf') else data

def git_source(ref, name):
    path = f'paper/ieee-paper/paper-{name}.tex'
    return record(f'{ref}-{name}.tex', f'{ref}:{path}', subprocess.check_output(['git','show',f'{ref}:{path}']))

def diff(name, a, b, an, bn):
    aa,bb=a.splitlines(True),b.splitlines(True)
    d=list(difflib.unified_diff(aa,bb,fromfile=an,tofile=bn,n=3))
    (OUT/name).write_text(''.join(d))
    manifest['diffs'][name]={'removed_lines':sum(x.startswith('-') and not x.startswith('---') for x in d),
                           'added_lines':sum(x.startswith('+') and not x.startswith('+++') for x in d),
                           'hunks':sum(x.startswith('@@') for x in d)}

aug = V/'01_review_materials/paper-build_MANUSCRIPT_2026-08-25.pdf'
record('august25.pdf',str(aug),aug.read_bytes())
txt = aug.with_suffix('.txt'); record('august25-provided.txt',str(txt),txt.read_bytes())
# Reading order instead of layout columns, for discovery comparisons only.
aug_text = subprocess.check_output(['pdftotext',str(aug),'-'],text=True)
record('august25-extracted.txt','pdftotext August PDF (default reading order)',aug_text.encode())
(OUT/'august25-extracted.txt').write_text(aug_text)
for name in ['access','build']:
    parent,current=git_source(PARENT,name),git_source(CURRENT,name)
    diff(f'parent-to-current-{name}.diff',parent,current,f'{PARENT}/paper-{name}.tex',f'{CURRENT}/paper-{name}.tex')
    if name=='build':
        # Deliberately preserve TeX syntax. No lossy conversion masquerades as rendered equality.
        diff('august-to-parent-build.cross-format.diff',aug_text,parent,'August25-PDF-extracted-reading-order',f'{PARENT}/paper-build.tex (RAW TEX; CROSS-FORMAT)')
        diff('august-to-current-build.cross-format.diff',aug_text,current,'August25-PDF-extracted-reading-order',f'{CURRENT}/paper-build.tex (RAW TEX; CROSS-FORMAT)')
    original=V/f'00_original_paper/paper-{name}-original.tex'
    record(f'original-{name}.tex',str(original),original.read_bytes())
for key,path in [('original.pdf',V/'00_original_paper/paper-build-original.pdf'),('existing-current.pdf',ROOT/'paper-build.pdf')]:
    record(key,str(path),path.read_bytes())
current_pdf_text=subprocess.check_output(['pdftotext',str(ROOT/'paper-build.pdf'),'-'],text=True)
diff('august-to-existing-current-pdf.diff',aug_text,current_pdf_text,'August25-PDF-extracted','existing-worktree-PDF-extracted (NOT a build of current TeX)')
manifest['fork_parent_pdf_present'] = bool(subprocess.check_output(['git','ls-tree',PARENT,'paper/ieee-paper/paper-build.pdf'],text=True).strip())
manifest['pdf_tools']=subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr.strip()
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
