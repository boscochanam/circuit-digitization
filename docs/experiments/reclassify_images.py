#!/usr/bin/env python3
"""CGHD1152 — corrected quality audit v4.
Re-classify images by paper type from existing VLM responses.
Use programmatic scores as fallback for VLM failures."""
import json, re
from collections import Counter

def load_json(path):
    with open(path) as f:
        text = f.read()
    text = re.sub(r',\s*\]', ']', text)
    text = re.sub(r',\s*\}', '}', text)
    return json.loads(text)

vlm_main = load_json('/home/claw/workspace/cghd_vlm_results.json')
vlm_retry = load_json('/home/claw/workspace/cghd_vlm_retry.json')

path_map = {}
for entry in vlm_main:
    path_map[entry['path']] = entry
for entry in vlm_retry:
    old = path_map.get(entry['path'], {}).get('vlm_response', '').strip()
    new = entry.get('vlm_response', '').strip()
    if new and len(new) > 10 and old in ('The', 'So', ''):
        path_map[entry['path']] = entry

sweep = load_json('/home/claw/workspace/cghd_quality_sweep.json')
sweep_map = {e['path']: e for e in sweep}

# Full paper-type classification patterns
PAPER_PATTERNS = {
    'graph': [
        'graph paper', 'grid paper', 'fine gray grid', 'grid of small black dots',
        'regular grid', 'dot grid', 'light grid', 'graph-paper',
        'blue grid', 'grid pattern', 'grid of fine lines', 'grid of dots',
        'background grid', 'gray grid lines', 'white grid', 'blue-tinted graph',
        'light blue grid', 'grid-patterned', 'subtle light grid',
        'blue grid-patterned', 'light grid pattern', 'grid background',
        'white graph paper', 'blue graph paper',
    ],
    'lined': [
        'lined paper', 'ruled paper', 'horizontal lines', 'notebook paper',
        'writing lines', 'college ruled', 'wide ruled', 'lined notebook',
        'ruled notebook', 'composition notebook', 'blue vertical lines',
        'light blue horizontal lines', 'red vertical lines', 'lined sheet',
        'ruled sheet', 'vertical blue lines', 'blue ruled', 'red margin',
        'ruled paper', 'lined page', 'blue horizontal lines',
        'horizontal blue lines', 'vertically lined', 'vertically ruled',
    ],
    'colored': [
        'blue paper', 'blue surface', 'solid blue', 'vibrant blue',
        'pink paper', 'green paper', 'colored paper', 'light blue paper',
        'blue background', 'light blue surface', 'pale blue',
        'light blue', 'blue-tinted',
    ],
    'textured': [
        'corrugated', 'fabric', 'carpet', 'wooden surface', 'rough texture',
        'cardboard', 'orange peel', 'textured surface', 'cloth',
        'orange paper', 'yellow paper', 'solid grey background',
        'grey background', 'gray textured', 'light gray textured',
        'vertical ridges', 'corrugated appearance', 'whiteboard',
        'whiteboard or similar', 'gray textured paper',
    ],
    'glare': ['glare', 'glossy', 'reflection', 'shiny'],
    'damaged': ['crumpled', 'wrinkled', 'creased', 'curling up', 'torn', 'folded', 'curling', 'bent corner'],
    'dark': ['too dark', 'very dark', 'underexposed', 'barely visible', 'poor lighting', 'extremely dark'],
    'obstructed': [
        'thumb', 'finger', 'fingers', 'hand holding', 'hand visible',
        'person holding', 'shadow of a hand', 'hand obstruct',
        'hand casting', 'hand at the', 'hand in the', 'finger at the',
        'fingertip', 'palm', 'hand covering',
    ],
    'plain_white': [
        'white paper', 'white background', 'white surface',
        'plain paper', 'plain white', 'clean white',
        'sheet of white paper', 'white sheet', 'plain white paper',
        'white piece of paper', 'off-white paper', 'white page',
        'white notebook paper', 'white, plain paper',
    ],
}

def classify_vlm(resp_lower, resp):
    if len(resp) < 10 or resp.strip() in ('The', 'So', ''):
        return ('vlm_failed', 'truncated')
    if resp.startswith('ERROR:'):
        return ('vlm_failed', 'zip_error')
    if '<point>' in resp or '"bbox_2d"' in resp:
        return ('vlm_failed', 'coordinate_output')

    # Check each paper type's patterns
    for paper_type, patterns in PAPER_PATTERNS.items():
        for p in patterns:
            if p in resp_lower:
                return (paper_type, p)

    # Fuzzy matches
    if 'grid' in resp_lower and any(w in resp_lower for w in ['paper', 'background', 'surface']):
        return ('graph', 'fuzzy_grid')
    if 'graph' in resp_lower:
        return ('graph', 'fuzzy_graph')
    if 'paper' in resp_lower and 'textured' in resp_lower:
        return ('textured', 'textured_paper')
    if 'whiteboard' in resp_lower:
        return ('textured', 'whiteboard')

    return ('unclear', 'no_pattern_match')

def classify_programmatic(prog):
    """Classify based on programmatic scores when VLM failed."""
    mean = prog.get('mean', 128)
    grid_score = prog.get('grid_score', 0)
    shadow_score = prog.get('shadow_score', 0)
    contrast = prog.get('contrast', 0.5)

    if mean < 60:
        return ('dark', 'programmatic_too_dark')
    if mean > 240:
        return ('glare', 'programmatic_overexposed')
    if contrast < 0.16:
        return ('dark', 'programmatic_low_contrast')
    if grid_score > 35:
        return ('likely_grid', f'programmatic_grid_{grid_score:.0f}')
    if shadow_score > 40:
        return ('shadow_issue', f'programmatic_shadow_{shadow_score:.0f}')

    return ('unknown', 'programmatic_no_issue')

def get_verdict(paper_type):
    reject = {'graph', 'lined', 'textured', 'damaged', 'obstructed',
              'glare', 'dark', 'likely_grid', 'shadow_issue'}
    if paper_type in reject:
        return 'REJECT'
    if paper_type == 'colored':
        return 'MARGINAL'
    if paper_type == 'plain_white':
        return 'GOOD'
    return 'NODATA'

results = []
for path, entry in path_map.items():
    resp = entry.get('vlm_response', '').strip()
    resp_lower = resp.lower()
    
    prog = sweep_map.get(path, {})
    
    paper_type, reason = classify_vlm(resp_lower, resp)
    
    # If VLM failed, fall back to programmatic
    if paper_type == 'vlm_failed':
        prog_type, prog_reason = classify_programmatic(prog)
        paper_type = prog_type
        reason = prog_reason
    
    verdict = get_verdict(paper_type)
    
    results.append({
        'path': path,
        'drafter': entry['drafter'],
        'filename': entry['filename'],
        'paper_type': paper_type,
        'reason': reason,
        'grid_score': prog.get('grid_score', 0),
        'mean_brightness': prog.get('mean', 128),
        'shadow_score': prog.get('shadow_score', 0),
        'verdict': verdict
    })

# Save
with open('/home/claw/workspace/cghd_reclassified.json', 'w') as f:
    json.dump(results, f, indent=2)

# Summaries
verdicts = Counter(r['verdict'] for r in results)
paper_types = Counter(r['paper_type'] for r in results)
reasons = Counter(r['reason'] for r in results)

print("=== Paper Type Distribution ===")
for pt, c in paper_types.most_common():
    print(f"  {pt:20s}: {c:3d}")

print("\n=== Verdict Distribution ===")
for v, c in verdicts.most_common():
    print(f"  {v:10s}: {c:3d}")

print(f"\nTotal: {len(results)}")

# Per-drafter
drafters = {}
for r in results:
    d = r['drafter']
    if d not in drafters:
        drafters[d] = {'GOOD': 0, 'MARGINAL': 0, 'REJECT': 0, 'NODATA': 0, 'total': 0, 'types': []}
    drafters[d][r['verdict']] += 1
    drafters[d]['total'] += 1
    drafters[d]['types'].append((r['paper_type'], r['reason']))

print(f"\n{'Drafter':12s} {'GOOD':>4s} {'MARG':>4s} {'REJ':>4s} {'NODATA':>6s} |  Primary Issues")
print('-' * 60)
for d in sorted(drafters.keys(), key=lambda x: int(x.split('_')[1]) if x.split('_')[1].lstrip('-').isdigit() else 999):
    info = drafters[d]
    type_counts = Counter(pt for pt, _ in info['types'])
    top = type_counts.most_common(3)
    top_str = ', '.join(f'{t}({c})' for t, c in top)
    print(f"{d:12s} {info['GOOD']:>4d} {info['MARGINAL']:>4d} {info['REJECT']:>4d} {info['NODATA']:>6d} | {top_str}")
