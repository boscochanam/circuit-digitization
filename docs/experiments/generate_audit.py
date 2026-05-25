#!/usr/bin/env python3
"""Generate the final corrected CGHD1152 quality audit report."""
import json, re
from collections import Counter

def load_json(path):
    with open(path) as f:
        text = f.read()
    text = re.sub(r',\s*\]', ']', text)
    text = re.sub(r',\s*\}', '}', text)
    return json.loads(text)

results = load_json('/home/claw/workspace/cghd_reclassified.json')

# Build per-drafter analysis
drafters = {}
for r in results:
    d = r['drafter']
    if d not in drafters:
        drafters[d] = {
            'samples': [], 'GOOD': 0, 'MARGINAL': 0, 'REJECT': 0, 'NODATA': 0,
            'types': Counter(), 'total': 0
        }
    drafters[d]['samples'].append(r)
    drafters[d][r['verdict']] += 1
    drafters[d]['total'] += 1
    drafters[d]['types'][r['paper_type']] += 1

# Sort samples by composite score descending (use grid_score as proxy - lower is better for plain white)
for d in drafters:
    drafters[d]['samples'].sort(key=lambda x: x['grid_score'])

# Generate verdict for each drafter
# A drafter is GOOD if >50% are GOOD or MARGINAL
# REJECT if >50% are REJECT
# MIXED otherwise
# NODATA if >50% NODATA

drafter_verdicts = {}
for d, info in drafters.items():
    total = info['total']
    good_pct = info['GOOD'] / total * 100
    marginal_pct = info['MARGINAL'] / total * 100
    reject_pct = info['REJECT'] / total * 100
    nodata_pct = info['NODATA'] / total * 100
    
    if nodata_pct >= 50:
        verdict = 'NODATA'
    elif good_pct + marginal_pct >= 50:
        verdict = 'KEEP'
    elif reject_pct >= 50:
        verdict = 'REJECT'
    else:
        verdict = 'MIXED'
    
    drafter_verdicts[d] = {
        'verdict': verdict,
        'good_pct': round(good_pct, 0),
        'marginal_pct': round(marginal_pct, 0),
        'reject_pct': round(reject_pct, 0),
        'nodata_pct': round(nodata_pct, 0),
        'counts': {'GOOD': info['GOOD'], 'MARGINAL': info['MARGINAL'], 'REJECT': info['REJECT'], 'NODATA': info['NODATA']},
        'top_types': dict(info['types'].most_common(3)),
        'primary_issue': info['types'].most_common(1)[0][0] if info['types'] else 'unknown'
    }

# Save audit
audit = {
    'total_images_sampled': len(results),
    'total_drafters': len(drafters),
    'drafters': drafter_verdicts,
    'recommended_keep': [d for d, v in drafter_verdicts.items() if v['verdict'] == 'KEEP'],
    'recommended_reject': [d for d, v in drafter_verdicts.items() if v['verdict'] == 'REJECT'],
    'recommended_mixed': [d for d, v in drafter_verdicts.items() if v['verdict'] == 'MIXED'],
    'recommended_nodata': [d for d, v in drafter_verdicts.items() if v['verdict'] == 'NODATA']
}

with open('/home/claw/workspace/cghd_final_audit.json', 'w') as f:
    json.dump(audit, f, indent=2, default=str)

# Print summary
print("=" * 60)
print("CGHD1152 CORRECTED QUALITY AUDIT — Paper-Type Based")
print("=" * 60)

print(f"\nSampled: {len(results)} images ({len(drafters)} drafters, 10 samples each)")
print()

for v in ['KEEP', 'MIXED', 'REJECT', 'NODATA']:
    drafters_in = audit[f'recommended_{v.lower()}']
    if drafters_in:
        print(f"  {v}: {', '.join(sorted(drafters_in, key=lambda x: int(x.split('_')[1]) if x.split('_')[1].lstrip('-').isdigit() else 999))}")

print()
print("--- Per-Drafter Detail ---")
print()
for d in sorted(drafter_verdicts.keys(), key=lambda x: int(x.split('_')[1].lstrip('-'))):
    v = drafter_verdicts[d]
    pt = v['primary_issue']
    c = v['counts']
    flag = '✅' if v['verdict'] == 'KEEP' else '⚠️' if v['verdict'] == 'MIXED' else '❌' if v['verdict'] == 'REJECT' else '❓'
    print(f"{flag} {d:12s} → {v['verdict']:6s}  (G={c['GOOD']}, M={c['MARGINAL']}, R={c['REJECT']}, ?={c['NODATA']})  Issue: {pt}")
