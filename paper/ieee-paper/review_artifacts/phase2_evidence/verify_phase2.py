"""Reuse the committed source/stored-JSON inspector without altering phase-1 evidence.

This is document inspection, not a benchmark or scientific test entry point.
Only the Gaussian display is now read from the corrected chart's extracted text.
"""
from pathlib import Path
import hashlib
import json
import subprocess

out = Path(__file__).resolve().parent
source = out.parent / 'verification_evidence/inspect_sources.py'
code = source.read_text()
stop = "(O/'inspection.json').write_text"
assert code.count(stop) == 1
code = code.split(stop)[0]
old = "check('wire_benchmark.pdf Gaussian label',path,'global_f1',d['global_f1'],'0.928')"
new = "check('wire_benchmark.pdf Gaussian label',path,'global_f1',d['global_f1'],re.search(r'adaptive Gaussian \\(skeleton\\)\\s+(\\d+\\.\\d+)',report['figures']['wire_benchmark'])[1])"
assert code.count(old) == 1
code = code.replace(old,new)
namespace = {}
exec(compile(code, str(source), 'exec'), namespace)
report = namespace['report']
report['triangle_boundary'] = 'Retain triangle_skeleton 0.758, explicitly labeled; no stored Triangle 0.795 config recovered in the searched records. See PHASE2_CHART.md.'
report['inspection_method'] = {'reused_inspector_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                             'changes': 'Gaussian display taken from PDF extraction; output redirected here; Triangle boundary updated. Original phase-1 report/script unchanged.'}
repo = Path('paper/ieee-paper')
protected = {}
for name in ['access','build']:
    path = f'paper/ieee-paper/paper-{name}.tex'
    current = Path(path).read_text()
    before = subprocess.check_output(['git','show',f'8f4e18b:{path}'],text=True)
    protected[name] = {
        'frontmatter_unchanged': current.split(r'\begin{abstract}')[0] == before.split(r'\begin{abstract}')[0],
        'acknowledgment_through_end_unchanged': current.split(r'\section*{Acknowledgment}')[1] == before.split(r'\section*{Acknowledgment}')[1],
    }
report['protected_fields'] = protected
report['changed_figure_paths'] = subprocess.check_output(['git','diff','--name-only','8f4e18b','--','paper/ieee-paper/figures'],text=True).splitlines()
report['experiment_tree_unchanged'] = subprocess.check_output(['git','rev-parse','8f4e18b:docs/research/experiments'],text=True) == subprocess.check_output(['git','rev-parse','HEAD:docs/research/experiments'],text=True)
assert all(all(v.values()) for v in protected.values())
assert report['changed_figure_paths'] == ['paper/ieee-paper/figures/wire_benchmark.pdf']
assert report['experiment_tree_unchanged']
assert all(x['status']=='PASS' for x in report['numbers'])
assert report['sources']['abstract_equal'] and report['sources']['body_equal_with_named_figure_exceptions'] and report['sources']['tables_equal']
(out/'inspection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'number_comparisons':len(report['numbers']), 'failures':sum(x['status']=='FAIL' for x in report['numbers']), 'abstract_equal':report['sources']['abstract_equal'], 'scientific_body_equal_with_figure_exceptions':report['sources']['body_equal_with_named_figure_exceptions'], 'tables_equal':report['sources']['tables_equal'], 'protected_fields':protected, 'changed_figures':report['changed_figure_paths'], 'experiment_tree_unchanged':report['experiment_tree_unchanged']},indent=2))
