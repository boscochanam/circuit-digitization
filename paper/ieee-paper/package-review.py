"""Assemble a coauthor handoff without modifying experimental evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--template-directory', type=Path, required=True)
args = parser.parse_args()
paper = Path(__file__).resolve().parent
root = paper.parent.parent
out = paper / 'output/pdf'
files = {}

def add(path, name):
    assert path.is_file(), path
    assert name not in files, name
    files[name] = path.read_bytes()

for name in ['paper-access.pdf', 'paper-access-highlighted.pdf', 'paper-build.pdf',
             'response-to-reviewers.pdf', 'reviewer-status-report.pdf',
             'graphical-abstract.pdf', 'changes-since-4d636d0.pdf',
             'changes-since-4d636d0.diff', 'reviewed-baseline-source.diff',
             'highlight-change-index.pdf', 'highlight-change-index.json',
             'response_page_map.json', 'page-checks.json',
             'paper-access.log', 'paper-build.log']:
    add(out / name, 'documents/' + name)
for name in ['paper-access.tex', 'paper-build.tex', 't1times.fd',
             'build-local.ps1', 'build-highlighted.py', 'build-review-artifacts.py',
             'package-review.py']:
    add(paper / name, 'source/paper/ieee-paper/' + name)
for path in (paper / 'figures').rglob('*'):
    if path.is_file() and path.suffix.lower() in {'.pdf', '.png', '.jpg', '.tex'}:
        add(path, 'source/paper/ieee-paper/' + path.relative_to(paper).as_posix())
for path in args.template_directory.iterdir():
    if path.is_file() and (path.suffix.lower() in {'.cls', '.sty', '.tfm', '.pfb', '.map', '.fd'}
                          or path.name in {'logo.png', 'bullet.png', 'notaglinelogo.png'}):
        add(path, 'template-support/' + path.name)
for name in ['CLOSEOUT_2026-09-24.md', 'INDIVIDUAL_VERIFICATION_2026-09-15.md',
             'RESPONSE_TO_REVIEWERS.md', 'REVIEWER_STATUS_REPORT.md', 'REVIEW_CHANGES.md']:
    add(paper / 'review_artifacts' / name, 'review/' + name)
add(root / 'output/baseline/pre-review.zip', 'baseline/source-33f5e3d.zip')
add(root / 'output/baseline/snapshot/paper/ieee-paper/paper-access.pdf', 'baseline/paper-access-33f5e3d.pdf')
files['README.txt'] = b'''IEEE Access coauthor review package - 24 September 2026

Start with documents/paper-access.pdf (11 pages).
Yellow highlights mark rendered text additions/replacements; orange page frames
mark changed figures. Deletions are recorded in highlight-change-index.pdf.
The full reviewed-baseline-source.diff preserves exact source changes.
Local edits since upstream 4d636d0 are separately recorded in changes-since-4d636d0.diff.
Reviewer mappings and open confirmations are in review/CLOSEOUT_2026-09-24.md.

Baseline: 33f5e3d37a85641b13bffaf7fc34b94eb5d35c47 (8 July 2026), selected
as the latest manuscript before the August 13 review return. This is not a
portal-certified submission identity. No new experiments were run.
Not submission-ready until author metadata, publication placeholders, Bosco's
personal provenance checks and final coauthor approval are resolved.

Rebuild manuscripts on Windows with installed pdfLaTeX and required packages:
cd source/paper/ieee-paper
./build-local.ps1 -TemplateDirectory ../../../template-support
Python rendering requires PyMuPDF, ReportLab, Pillow and Windows Segoe UI fonts.
The comparison scripts additionally require the Git repository/history and the
baseline snapshot at their documented paths; this ZIP is not a Git checkout.

SHA256SUMS.txt lists every other member's SHA-256 digest.
'''
files['SHA256SUMS.txt'] = ''.join(
    f'{hashlib.sha256(data).hexdigest()}  {name}\n'
    for name, data in sorted(files.items())).encode()
target = paper / 'output/IEEE_Access_Coauthors_2026-09-24.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, data in sorted(files.items()):
        archive.writestr(name, data)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for name, data in files.items():
        assert archive.read(name) == data, name
print(json.dumps({'zip': str(target), 'members': len(files),
                  'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}, indent=2))
