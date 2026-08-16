# Detected-box join eval (N=31)

Model: `models/component_detection/yolo26m_obb_16class_aug.pt` conf=0.5, IoU match thresh=0.3

Runtime: 38.2s total, 1.23s/image


## Join F1 (component-pair, detected boxes)

| strategy | microF1 | microP | microR | macroF1 |
|---|---|---|---|---|
| scale_completion | 0.247 | 0.298 | 0.211 | 0.324 |
| scale_completion_w | 0.245 | 0.296 | 0.209 | 0.322 |

## Component detection quality (electrical subset)

P=0.612 R=0.655 F1=0.632 (gt=226, det=242, matched=148)


## Worst images (primary strategy)

| image | f1 | p | r | gt_elec | det_elec |
|---|---|---|---|---|---|
| C28_D1_P3_jpg | 0.0 | 0.0 | 0.0 | 14 | 12 |
| C5_D1_P1_jpg | 0.0 | 0.0 | 0.0 | 3 | 0 |
| C10_D2_P3_jpg | 0.0 | 0.0 | 0.0 | 4 | 0 |
| C4_D2_P4_jpg | 0.0 | 0.0 | 0.0 | 4 | 3 |
| C15_D2_P2_jpg | 0.065 | 0.077 | 0.056 | 7 | 7 |
| C37_D2_P4_jpg | 0.074 | 0.25 | 0.043 | 11 | 11 |
| C66_D2_P4_jpg | 0.081 | 0.056 | 0.146 | 12 | 18 |
| C77_D2_P2_jpg | 0.087 | 0.107 | 0.073 | 14 | 20 |
