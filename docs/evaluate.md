# Evaluation

The evaluation framework compares detected lines against ground truth using a line-distance metric and greedy matching.

## Usage

```bash
wire-eval --dataset hand_drawn --backend contour

# Evaluate specific config
wire-eval \
  --dataset hand_drawn \
  --params '{"threshold": {"mode": "otsu"}, "dilate": {"kernel_size": 5}}'
```

## Metrics

### Line Distance

The distance between a detected segment D(p1,p2) and ground truth segment G(g1,g2) is the average of the point-to-segment distances from D's endpoints to G:

```
segment_dist(D, G) = (point_to_segment_dist(p1, g1, g2) + point_to_segment_dist(p2, g1, g2)) / 2
```

### Classification

A detection is classified using greedy matching with a distance threshold:

| Category | Condition |
|----------|-----------|
| **True Positive (TP)** | `segment_dist(D, G) ≤ threshold` for some unmatched GT |
| **Redundant** | Multiple detections matching the same GT |
| **False Positive (FP)** | Detection with no matching GT within threshold |
| **False Negative (FN)** | Unmatched ground truth lines |

### Aggregate Metrics

```
Recall    = TP / (TP + FN)
Precision = TP / (TP + FP + Redundant)
F1        = 2 × (Recall × Precision) / (Recall + Precision)
```

The default distance threshold is 20 pixels.

## Output

The evaluation produces per-image results and an aggregate report:

```
Dataset: hand_drawn (140 images)
Backend: contour
Params:  {threshold: otsu, dilate_ksize: 5, ...}
────────────────────────────────────────────
TP:  5,734    FN:  1,360    Recall:  0.808
FP:    939    Redundant:  304    Precision:  0.819
                 F1:  0.814
────────────────────────────────────────────
```

Reports can be exported as CSV and markdown.
