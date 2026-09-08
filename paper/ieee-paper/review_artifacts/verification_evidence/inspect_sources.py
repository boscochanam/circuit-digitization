"""Read stored evidence and source text only; never import/run the scientific pipeline.

Run from the repository root. Writes this directory's inspection.json.
External input paths deliberately match the supplied verification evidence pack.
This records observations, not an automatic semantic/editorial PASS.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess

P = Path('paper/ieee-paper')
O = P / 'review_artifacts/verification_evidence'
E = Path('docs/research/experiments')
V = Path('/home/claw/circuit-digitization-validation-20260907')
S = V / 'notes/scratch'
K = V / 'context/01_review_materials'
report = {'verified_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'hashes': {}, 'numbers': [], 'sources': {}, 'figures': {}}


def read(path):
    data = path.read_bytes()
    report['hashes'][str(path)] = hashlib.sha256(data).hexdigest()
    return data.decode()


def stored(path):
    return json.loads(read(path))


def check(anchor, path, key, value, display):
    actual = format(value, '.' + str(len(display.partition('.')[2])) + 'f') if '.' in display else str(value)
    report['numbers'].append(dict(anchor=anchor, path=str(path), key=key,
                                  stored=value, display=display,
                                  status='PASS' if actual == display else 'FAIL'))


def norm(s):
    return ' '.join(s.split())


def uncomment(s):
    return re.sub(r'(?<!\\)%[^\n]*', '', s)


a, b = (read(P / f'paper-{name}.tex') for name in ['access', 'build'])
r = read(P / 'review_artifacts/RESPONSE_TO_REVIEWERS.md')
body = lambda s: uncomment(s[s.index(r'\section{Introduction}'):s.index(r'\begin{thebibliography}')])
canon = lambda s: re.sub(r'\\(?:input|includegraphics)(?:\[[^]]*\])?\{figures/(pipeline_overview|endpoint_graph|completion)(?:_tikz\.tex|\.pdf)\}', r'FIGURE_DEPENDENCY:\1', s)
report['sources']['abstract_equal'] = norm(re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', a, re.S)[1]) == norm(re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', b, re.S)[1])
report['sources']['body_equal_without_figure_exceptions'] = norm(body(a)) == norm(body(b))
report['sources']['body_equal_with_named_figure_exceptions'] = norm(canon(body(a))) == norm(canon(body(b)))
for name, text in [('A', a), ('B', b)]:
    clean = uncomment(text)
    labels = re.findall(r'\\label\{([^}]+)\}', clean)
    refs = re.findall(r'\\(?:ref|eqref|pageref)\{([^}]+)\}', clean)
    cites = [k.strip() for block in re.findall(r'\\cite\{([^}]+)\}', clean) for k in block.split(',')]
    bib = re.findall(r'\\bibitem\{([^}]+)\}', clean)
    report['sources'][name] = dict(label_count=len(labels), duplicate_labels=[k for k,v in collections.Counter(labels).items() if v > 1],
                                  unresolved_refs=sorted(set(refs)-set(labels)), unresolved_citations=sorted(set(cites)-set(bib)),
                                  uncited_bibitems=sorted(set(bib)-set(cites)), bibliography_order=bib,
                                  first_citation_order=list(dict.fromkeys(cites)))
    report['sources'][name]['table_blocks'] = re.findall(r'\\begin\{tabular\}.*?\\end\{tabular\}', clean, re.S)
report['sources']['tables_equal'] = report['sources']['A'].pop('table_blocks') == report['sources']['B'].pop('table_blocks')

letter = read(K / 'decision-email-raw.txt').split('===SEPARATOR===')[0]
concerns = re.findall(r'\*\*Reviewer concern:\*\* (.*?)(?=\n\n\*\*Author response:)', r, re.S)
originals = []
for n in [1, 2]:
    block = letter.split(f'Reviewer: {n}', 1)[1].split('Additional Questions:', 1)[0]
    originals.extend(re.findall(r'^\d\.\s*(.*?)(?=^\d\.|\Z)', block, re.M | re.S))
report['sources']['response'] = dict(headings=re.findall(r'### Reviewer#(\d), Concern # (\d)', r),
    concerns=len(concerns), verbatim_concerns=[norm(x)==norm(y) for x,y in zip(concerns, originals)],
    original_concerns=len(originals), responses=len(re.findall(r'\*\*Author response:\*\* \S',r)),
    actions=len(re.findall(r'\*\*Author action:\*\* \S',r)))
for file in [K/'IEEE_Access_Response_to_Reviewers_TEMPLATE.txt', V/'notes/IMPLEMENTATION_PLAN.md', V/'notes/PLAN_REDTEAM.md', O/'amended-plan.md']:
    read(file)
for file in [K/'IEEE_Access_Response_to_Reviewers_TEMPLATE.pdf']:
    report['hashes'][str(file)] = hashlib.sha256(file.read_bytes()).hexdigest()

patterns = [r'statistically indistinguishable', r'same accuracy', r'far more expensive', r'two to three orders', r'100[–-]1000',
            r'structurally guaranteed', r'structurally.valid.by.construction', r'largely solved', r'primary failure mode',
            r'dominant failure mode', r'without over.merging', r'prevents?\b.{0,35}short', r'rules? out.{0,35}bias',
            r'upper bounds?', r'\bfair\w*', r'guarantee\w*', r'\bequivalence\b', r'SPICE.{0,8}Netlists?',
            r'simulation.ready', r'completion masks', r'same floating pins', r'endpoint.drop', r'0\.247']
report['claim_patterns'] = patterns
report['claim_hits'] = []
for file in [P/'paper-access.tex',P/'paper-build.tex',P/'review_artifacts/RESPONSE_TO_REVIEWERS.md',*sorted((P/'figures').glob('*_tikz.tex'))]:
    text = read(file)
    for line_no, line in enumerate(text.splitlines(),1):
        hits=[pat for pat in patterns if re.search(pat,norm(line),re.I)]
        if hits: report['claim_hits'].append(dict(file=str(file),line=line_no,patterns=hits,text=line))
for name in ['pipeline_overview','endpoint_graph','completion','wire_benchmark','join_comparison','real_join_comparison','complexity_histogram']:
    file=P/'figures'/f'{name}.pdf'
    data=file.read_bytes(); report['hashes'][str(file)]=hashlib.sha256(data).hexdigest()
    proc=subprocess.run(['pdftotext','-layout',str(file),'-'],check=True,capture_output=True,text=True)
    report['figures'][name]=proc.stdout

path=E/'join_micro_n31.json'; j=stored(path)
for strategy, values in {'scale_completion':['0.890','0.919','0.864','0.901'], 'degree_budget':['0.829','0.789','0.874','0.853'], 'graph_scale':['0.816','0.929','0.727','0.838'], 'graph_rescue':['0.787','0.811','0.764','0.813'], 'production':['0.667','0.698','0.638','0.674']}.items():
    for key,value in zip(['f1','p','r'],values): check('tab:real_join',path,f'micro.{strategy}.{key}',j['micro'][strategy][key],value)
    check('tab:real_join',path,f'macro.{strategy}.f1',j['macro'][strategy]['f1'],values[3])
check('Conclusion',path,'micro.scale_completion.f1',j['micro']['scale_completion']['f1'],'0.8903')
counts=[x['comps'] for x in j['per_image'].values()]
report['complexity_inventory']=dict(n=len(counts),min=min(counts),max=max(counts),median=statistics.median(counts),at_most_five=sum(c<=5 for c in counts),at_least_ten=sum(c>=10 for c in counts))
path=E/'bootstrap_ci_n31.json'; d=stored(path)
for key,fields in {'join/scale_completion':{'lo':'0.855','hi':'0.924'},'VLM_minus_ours_micro':{'point':'0.033','lo':'-0.009','hi':'0.078'}}.items():
    obj=d[key]['micro'] if key.startswith('join/') else d[key]
    for field,display in fields.items():check('Abstract; real/VLM evaluation',path,key+('.micro.' if key.startswith('join/') else '.')+field,obj[field],display)
path=E/'vlm_clean_rerun_n31.json';d=stored(path)
for field,display in [('F1','0.923'),('P','0.970'),('R','0.880')]:check('tab:real_join; VLM',path,'micro.'+field,d['micro'][field],display)
check('tab:real_join; VLM',path,'macro_f1',d['macro_f1'],'0.949')
check('VLM',path,'n',d['n'],'31')
check('VLM',path,'count(rows with stored F1 == 1)',sum(row['F1']==1 for row in d['rows']),'21')
path=E/'revision_evidence/edge_ablation_results.json';d=stored(path)
for block, rows in d.items():
    for name,row in rows.items():
        full=block.startswith('full'); fixed=name=='scale_rel_off_fixedpx'
        fields={'f1':'0.890' if full else ('0.820' if fixed else '0.816'), 'tp':'418' if full else ('356' if fixed else '352'), 'fp':'37' if full else ('28' if fixed else '27'), 'fn':'66' if full else ('128' if fixed else '132')}
        if full: fields.update(p='0.919',r='0.864')
        for field,display in fields.items():check('tab:edge_ablation',path,f'{block}.{name}.micro.{field}',row['micro'][field],display)
path=E/'join_reach_sweep_n31.json';d=stored(path)
report['reach_macro']={key:d[key]['f1'] for key in [f'db_scale_r{x:.1f}' for x in [3,3.5,4,4.5,5]]}
check('reach sweep',path,'min(selected stored f1)',min(report['reach_macro'].values()),'0.895')
check('reach sweep',path,'max(selected stored f1)',max(report['reach_macro'].values()),'0.903')
path=E/'drafter_map_n31.json'; d=stored(path)
report['drafter_counts']=dict(collections.Counter(d.values()))
report['drafter_stored_count_sums']={group:{field:sum(j['per_image'][image]['scale_completion'][field] for image in d if d[image]==group) for field in ['tp','fp','fn']} for group in ['drafter_1','drafter_2','drafter_10','drafter_12']}
path=E/'synthetic_leaderboard.json';d=stored(path)
for strategy,displays in {'scale_completion':['1.00','1.00','1.00','0.96','0.95'],'degree_budget':['1.00','1.00','1.00','0.95','0.94'],'graph_rescue':['1.00','1.00','1.00','0.94','0.90'],'graph_scale':['1.00','1.00','1.00','0.94','0.85'],'production':['1.00','0.97','0.90','0.56','0.36']}.items():
    row=next(x for x in d if x['strategy']==strategy)
    for level,display in enumerate(displays):check('tab:join_leaderboard',path,f'[strategy={strategy}].by_severity[{level}]',row['by_severity'][level],display)
path=S/'fresh-join-ablation.json';d=stored(path)
for field,display in [('f1','0.8898'),('p','0.913'),('r','0.868'),('tp','420'),('fp','40'),('fn','64')]:check('perfect-wire reference',path,'perfect.'+field,d['perfect'][field],display)
report['crossover_summary']=d['crossover']
path=S/'historical-wire-config.json';d=stored(path)
for i,values in [(0,['0.973','0.974','0.972']),(1,['0.976','0.973','0.978'])]:
    for field,display in zip(['global_f1','precision','recall'],values):check('tab:wire_benchmark',path,f'[{i}].{field}',d[i][field],display)
    for field,display in [('dedup_angle','10'),('dedup_dist','18')]:check('wire configuration',path,f'[{i}].config.{field}',int(d[i]['config'][field]),display)
check('wire prose',path,'[1].global_f1',d[1]['global_f1'],'0.9755')
report['wire_inventory']=dict(n=len(d[1]['images']),median=statistics.median(x['f1'] for x in d[1]['images']),at_least_90=sum(x['f1']>=.9 for x in d[1]['images']))
path=S/'wire-rerun.json';d=stored(path)
check('wire prose',path,'[0].global_f1',d[0]['global_f1'],'0.9726')
for field,display in [('dedup_angle','12'),('dedup_dist','8')]:check('wire configuration',path,'[0].config.'+field,d[0]['config'][field],display)
for field,display in [('global_f1','0.789'),('precision','0.796'),('recall','0.783')]:check('tab:wire_benchmark Otsu',path,'[2].'+field,d[2][field],display)
path=S/'crossover-causal.json';d=stored(path)['C242_D1_P1_jpg']
for name,values in [('baseline',[27,4,0]),('no_crossing_type2',[19,0,8])]:
    for field,display in zip(['tp','fp','fn'],values):check('C242 Discussion; R2-4',path,'C242_D1_P1_jpg.'+name+'.'+field+(' (list length)' if field!='tp' else ''),d[name][field] if field=='tp' else len(d[name][field]),str(display))
report['removed_edges']=d['removed_edges']
for filename,key in [('cc_detected_micro_n31.json','detCCL_d15'),('hough_micro_n31.json','link44_reach48')]:
    path=E/filename;d=stored(path);row=d[key] if filename.startswith('cc') else d['configs'][key]
    values=['0.624','0.965','0.461','0.611'] if filename.startswith('cc') else ['0.805','0.750','0.868','0.847']
    for field,display in zip(['f1','p','r'],values):check('tab:real_join',path,key+'.micro.'+field,row['micro'][field],display)
    check('tab:real_join',path,key+'.macro.f1',row['macro']['f1'],values[3])
path=E/'per_circuit_scale_completion_l4_n16.json';d=stored(path)
for name,values in {'parallel_rr':['1.00','1.00','25'],'divider_rr':['0.99','1.00','69'],'rl_series':['0.99','1.00','81'],'diode_r':['0.99','1.00','69'],'dense_pair':['0.93','0.90','12'],'loop4_r':['0.94','0.91','56'],'wheatstone':['0.82','0.85','6'],'ring6_r':['0.95','0.92','50']}.items():
    for field,display in zip(['f1','precision'],values):check('tab:per_circuit',path,f'per_circuit.{name}.{field}',d['per_circuit'][name][field],display)
    check('tab:per_circuit',path,f'round(100 * per_circuit.{name}.sim_ok_rate), ties-to-even',round(100*d['per_circuit'][name]['sim_ok_rate']),values[2])
recovered = Path('/home/claw/circuit-digitization/output/benchmark_experiments/expanded_full_ranking')
for name,values in {'best_candidate_v1':['0.950','0.921','0.980'], 'best_candidate_v2':['0.959','0.944','0.974'], 'best_candidate_v3':['0.949','0.923','0.976']}.items():
    path=recovered/name/'summary.json';d=stored(path)
    for field,display in zip(['global_f1','precision','recall'],values):check('wire table / alternative figure row',path,field,d[field],display)
path=recovered/'adaptive_gaussian_skeleton/summary.json';d=stored(path)
check('wire prose',path,'global_f1',d['global_f1'],'0.845')
check('wire_benchmark.pdf Gaussian label',path,'global_f1',d['global_f1'],'0.928')
path=recovered/'triangle_skeleton/summary.json';d=stored(path)
check('wire_benchmark.pdf Triangle label (this stored config)',path,'global_f1',d['global_f1'],'0.758')
report['triangle_boundary']='The prior REVIEW_CHANGES.md claims corrected Triangle 0.795, but the recovered triangle_skeleton summary stores 0.7582635. Do not silently replace it without identifying the intended configuration.'
(O/'inspection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'numeric_checks':len(report['numbers']),'numeric_failures':[x for x in report['numbers'] if x['status']=='FAIL'], 'sources':report['sources'],'complexity':report['complexity_inventory'],'wire_inventory':report['wire_inventory'],'drafter_counts':report['drafter_counts'],'drafter_stored_count_sums':report['drafter_stored_count_sums']},indent=2))
