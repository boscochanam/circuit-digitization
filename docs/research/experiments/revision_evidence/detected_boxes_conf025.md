# Detected-box join eval (N=31)

Model: `models/component_detection/yolo26m_obb_16class_aug.pt` conf=0.25, IoU match thresh=0.3

Runtime: 36.2s total, 1.17s/image


## Join F1 (component-pair, detected boxes)

| strategy | microF1 | microP | microR | macroF1 |
|---|---|---|---|---|
| scale_completion | 0.244 | 0.268 | 0.223 | 0.340 |
| scale_completion_w | 0.242 | 0.266 | 0.221 | 0.338 |

## Component detection quality (electrical subset)

P=0.590 R=0.695 F1=0.638 (gt=226, det=266, matched=157)


## Worst images (primary strategy)

| image | f1 | p | r | gt_elec | det_elec |
|---|---|---|---|---|---|
| C10_D2_P3_jpg | 0.0 | 0.0 | 0.0 | 4 | 1 |
| C4_D2_P4_jpg | 0.0 | 0.0 | 0.0 | 4 | 3 |
| C15_D2_P2_jpg | 0.056 | 0.056 | 0.056 | 7 | 8 |
| C77_D2_P2_jpg | 0.075 | 0.077 | 0.073 | 14 | 23 |
| C66_D2_P4_jpg | 0.081 | 0.056 | 0.146 | 12 | 18 |
| C33_D2_P2_jpg | 0.118 | 0.182 | 0.087 | 10 | 10 |
| C28_D1_P3_jpg | 0.12 | 0.125 | 0.115 | 14 | 19 |
| C37_D2_P4_jpg | 0.143 | 0.4 | 0.087 | 11 | 13 |
