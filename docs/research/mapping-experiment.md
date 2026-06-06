# Wire-to-Component Mapping Experiment — Synthesis

## Summary

Comprehensive testing of 25+ methods for mapping wire endpoints to components across 134 images (7,048 endpoints, 3,524 wires).

## Key Results

### Best Method: Selective Disambiguation (threshold=30)

| Metric | Baseline | Best Method | Improvement |
|--------|----------|-------------|-------------|
| **Endpoint accuracy (GT)** | 91.93% | **93.10%** | +1.17% |
| **Wire accuracy (GT)** | 85.39% | **88.93%** | +3.54% |
| **Endpoint accuracy (detected)** | 94.38% | **94.88%** | +0.50% |
| **Wire accuracy (detected)** | 90.31% | **91.91%** | +1.60% |
| **Same-component errors** | 425 | **143** | -66% |

### Method Comparison (GT Wires, Endpoint Accuracy)

| Rank | Method | EP Accuracy | Wire Both | Same-Comp |
|------|--------|-------------|-----------|-----------|
| 1 | **selective_30** | **93.10%** | **88.93%** | 143 |
| 2 | selective_25 | 92.58% | 88.37% | 169 |
| 3 | selective_20 | 92.42% | 88.08% | 195 |
| 4 | selective_15 | 92.31% | 87.74% | 226 |
| 5 | selective_10 | 92.24% | 87.26% | 268 |
| 6 | baseline | 91.93% | 85.39% | 425 |
| 7 | disambiguate_two_terminal | 91.78% | 85.24% | 403 |
| 8 | ensemble_vote | 91.77% | 85.22% | 404 |
| 9 | disambiguate_smart | 91.63% | 87.29% | 184 |
| 10 | disambiguate_always | 90.22% | 85.30% | 0 |

## How Selective Disambiguation Works

The algorithm applies disambiguation only when ALL of these conditions are met:
1. Both wire endpoints map to the same component
2. The component is NOT a multi-terminal type (ICs, transistors)
3. Neither endpoint is inside the component polygon
4. For 2-terminal components: always disambiguate
5. For unknown types: only if the alternative is within threshold (30px)

This preserves legitimate same-component connections (e.g., two pins on an IC) while fixing wrong self-loops.

## Error Analysis

**Remaining 486 errors (6.9%) breakdown:**
- **67.7% near-miss**: Correct component is 2nd closest (would improve to 97.77% if fixed)
- **64.4% dense areas**: 3+ components within 50px
- **24.9% junction confusion**: Junctions/terminals involved
- **23.5% far endpoint**: Endpoint >50px from all components

**Why near-miss is hard to fix:**
- Direction-based correction: **worse** (77.37%) — wire direction doesn't indicate target
- Containment-based: no improvement — endpoints are rarely inside polygons
- The 2nd-closest component has no distinguishing signal from the 1st

## What DIDN'T Work

| Approach | Result | Why |
|----------|--------|-----|
| Pin templates (OBB-based) | 85.40% | OBB geometry ≠ actual pin positions |
| Image overlap | 91.37% | Wires connect at edges, not through polygons |
| Ray casting | 78.63% | Straight rays miss curved wire paths |
| Hungarian global | 66.54% | Over-optimization, removes valid same-comp |
| Direction near-miss | 77.37% | Wire direction ≠ target component direction |
| Polygon distance | 91.53% | Slightly worse than bbox for this task |
| Weighted polygon | 86.95% | Hybrid adds noise |

## What DID Work

| Approach | Key Insight |
|----------|-------------|
| **Selective disambiguation** | Only fix same-component when confident alternative exists |
| **Containment check** | Don't disambiguate if both endpoints inside polygon |
| **Type-aware logic** | Multi-terminal components can have same-comp wires |
| **Confidence threshold** | Gap between 1st and 2nd candidate determines action |

## Practical Recommendations

1. **Use selective disambiguation with threshold=30** as the default mapping method
2. **Filter same-component errors** in post-processing (143 remaining)
3. **Accept ~7% endpoint error rate** as the ceiling for distance-based methods
4. **For SPICE netlist**: 88.93% of wires will have correct connections

## Files

- `mapping_experiment_v2.py` — Phase 1: 20 distance/direction/OBB methods
- `mapping_phase2.py` — Phase 2: Dense area disambiguation
- `mapping_phase3.py` — Phase 3: Smart selective disambiguation + threshold sweep
- `mapping_phase4.py` — Phase 4: Pin templates, image verification
- `check_mapping_status.py` — Cron monitoring script

## Conclusion

**Selective disambiguation (threshold=30) is the recommended method.** It achieves:
- 93.10% endpoint accuracy on GT wires
- 94.88% endpoint accuracy on detected wires
- 88.93% wire accuracy (both endpoints correct)
- 143 same-component errors (down from 425)

The remaining 6.9% errors are in genuinely ambiguous cases (dense areas, near-miss) that cannot be resolved with distance-based methods alone. Further improvement would require:
- Pin-level annotations (ground truth pin locations)
- Circuit topology constraints
- Learned mapping models
