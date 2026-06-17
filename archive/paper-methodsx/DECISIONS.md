# Paper Decisions — MethodsX Submission

Confirmed by Bosco, June 2026.

## Naming

- **Method:** Degree-Budget Topology Join
- **System:** CircuitDigitizer
- **Metrics:** Wire F1 (primary) + Circuit Connectivity (secondary)

## Authors

1. Bosco Chanam (corresponding) — SCAAI, SIT Pune
2. Chris Dcosta — SCAAI, SIT Pune
3. Pranavesh Kumar Talupuri — USC

## Key Numbers

- Detection F1: 0.9755 (a16, 134 images)
- Connectivity: degree_budget 81.9% vs graph_rescue 68.8%
- Component detector: YOLO26M-OBB, 16-class, 88.5% mAP50

## Status

Current draft (`main.tex`) describes the old skeleton pipeline.
Needs rewrite before submission — degree_budget is the actual method.
