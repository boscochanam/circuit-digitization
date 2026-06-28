# Literature review — connectivity extraction for hand-drawn circuit→netlist

Focus: the **wire/connectivity ("joining") step**. Compiled 2026-06-28 (agent-assisted,
arXiv-verified for the load-bearing cites). For the paper's related work + baseline selection.

## Top-line findings
1. **CGHD + the Bayer et al. pipeline is the only serious public hand-drawn circuit-specific
   image→graph line of work** → our natural baseline + citation anchor (we use CGHD).
2. **No published paper reports a quantitative net-level / connectivity accuracy (edge-F1 or
   net-F1) on HAND-DRAWN circuits.** Bayer evaluates detection/segmentation/orientation; the
   connectivity step is only qualitative. **This is the gap our paper fills** with the
   human-verified net-GT benchmark + component-pair-F1 metric.
3. **Cross-paper accuracy numbers are NOT comparable** (different test sets + metric
   definitions: net acc vs confusion-F1 vs graph-edit-distance vs link-AUC vs SPICE Pass@k).
4. **Recurring reproducible recipe** (AMSnet 1.0, SINA, Reddy&Panicker, Bayer, Hemker):
   detect components → erase/mask them → connected-components (or Hough) on residual wire
   pixels → each blob = one net → assign each terminal to the net region it touches.

## Method table
| # | Citation | Detection | Connectivity | Dataset | Metric | Drawn |
|---|---|---|---|---|---|---|
|1|Bayer, van Waveren, Dengel — Modular Graph Extraction, ICDAR 2024, arXiv:2402.11093|Faster R-CNN; junctions/crossovers as classes|U-Net stroke seg → erase boxes → CCL on wires → blob touching 2 objs = edge|CGHD|det mAP 18%, seg 98.16%; **no connectivity metric**|Yes|
|2|Bayer, Roy, Dengel — Instance-Seg Graph Extraction, ICPRAM 2023, arXiv:2301.03155|Mask R-CNN|instance masks → keypoint endpoint→terminal matching|CGHD|no numeric connectivity metric|Yes|
|3|Thoma, Bayer, Li, Dengel — CGHD dataset, ICDAR-W 2021, arXiv:2107.10373|Faster R-CNN baseline|(dataset)|CGHD|~3,173 imgs/59 cls|Yes|
|4|Reddy & Panicker, SN Comput. Sci. 2022, arXiv:2106.11559|YOLOv5, mAP 98.1%|mask boxes → Hough H/V → line-intersection nodes → dilate+contour merge → nearest-terminal|154 drawn (private)|80% full reconstruction|Yes|
|5|Edwards & Chandran, ICASSP 2000, DOI 10.1109/ICASSP.2000.860185|moments+line feats|skeletonize → pixel-stack walk → syntactic node class|449 comps|86% comp / 92% node|Yes|
|6|AMSNet 1.0 — Tao et al., IEEE LAD 2024, arXiv:2405.09045|YOLOv8 97.1%|binarize → mask → flood-fill nets → 2D-conv crossing detect|~792 printed|net acc 96.7%|No|
|7|AMSnet 2.0 — Shi et al. 2025, arXiv:2505.09155|YOLO11 + junction dots|U-Net wire seg → CCL → angle-ordering|2,686|net F1 80–90%|No|
|8|SINA — Aldowaish et al. 2026, arXiv:2601.22114|YOLOv11 + GPT-4o verify|mask → CCL on wires → keep regions touching ≥2 comps → merge gnd → terminal map|700+ train (mixed drawn), 40 eval|netlist 96.47%|Yes(mixed)|
|9|Masala-CHAI — Bhandari et al. 2024, arXiv:2411.14299|YOLOv8|Deep Hough line priors → cluster endpoints <40px → GPT-4o assembly|7,500 printed|Pass@k downstream|No|
|10|Hu, Zhan, Tong — GAT, Sensors 2024, DOI 10.3390/s24010227|Swin, mAP 90.3%|ports=nodes; VGAE+GAT learned link prediction|1,200/3,552 (printed)|link AUC 93.4%|No|
|12|DiagramNet — Schäfer & Stuckenschmidt, ICDAR 2021, DOI 10.1007/978-3-030-86549-8_39|shape+degree predictor|visual arrow-relation + degree-constrained opt|hdBPMN (flowcharts)|beats Sketch2BPMN|Yes(flowcharts)|
|13|Hemker et al., Adv. Radio Sci. 2024, DOI 10.5194/ars-22-61-2024|YOLOv7|L-CNN lines → axis-aligned → center/endpoint match|164 printed PDF|mAP95 ≥0.73|No|

LLM/VLM leads (proprietary, weak as open baselines): AnalogMaster (arXiv:2604.20916, GPT-5
92.9% Pass@1), AMSnet-KG (2411.13560), AMSnet-q (2605.01404), AnalogRetriever (2604.23195).
Other drawn datasets: Digitize-HCD (Data in Brief 2025, 1,277 imgs), JUHCCR-v1 (Sci Rep 2025).

## Reproducible connectivity baselines (for our comparison)
**B1 — CCL net-tracing (SINA / AMSnet / Bayer "erase-and-label"). PRIMARY baseline.**
Erase component boxes → `cv2.connectedComponents` on residual dark pixels → blob touching ≥2
terminals = net → assign each terminal to the overlapping blob → merge grounds. ~150–250 LOC,
deterministic. Failure mode: crossing wires falsely merge (why Bayer/AMSnet detect crossovers).

**B2 — Hough + line-intersection nodes (Reddy & Panicker).** mask → HoughLinesP → classify H/V
→ constrained line intersections → dilate/contour merge into nodes → nearest-terminal map.
Breaks on diagonal/curved wiring.

**B3 — Skeleton pixel-walk (Edwards).** skeletonize wires-only mask → DFS the skeleton breaking
at branch/endpoint pixels → segments at a junction = one node. Covers diagonal/curvy wires.

## Skeptical flags
- Metrics not comparable across papers; never put net-acc/F1/GED/AUC/Pass@k in one ranked column.
- SINA's "2.72× over Masala-CHAI" is SINA's own re-eval on 40 author-curated schematics — favorable framing, not independent.
- Masala-CHAI reports no standalone connectivity accuracy; sizes inconsistent (2,100 vs 7,500); retitled from "Auto-SPICE".
- CGHD size varies by snapshot (1,152→~3,173); license conflict (CC-BY-4.0 vs CC0); netlist GT partial. State the version downloaded.
- DiagramNet / P&ID GNNs / Pan et al. (2504.10240, netlist-in) are cross-domain or wrong-modality → related work only.

## Addendum (2026-06-28): Peker et al. — closest contemporary (user-flagged, agent missed it)
**Peker, Toker, Öcal, Dalyan, Afacan, Gökdel**, "A Fully Automated SPICE-Compatible Netlist
Extraction From Image Using Deep Learning and Image Preprocessing Techniques," *IEEE Access*
vol. 14, pp. 19750–19765, 2026, doi:10.1109/ACCESS.2026.3656316. Accepted Jan 2026.
- **Task:** image→SPICE, printed + hand-drawn, transistor-level MOSFET analog (diff amps, OTAs,
  comparators). Their OWN dataset: 7 hand-drawn topologies, 354 participants, 4248 train/1062 val,
  300 test from 3 unseen topologies. NOT CGHD.
- **Detection:** YOLOv8/10/11 (transistor det, terminal seg, voltage seg, ground det), mAP 96–99%.
- **Connectivity:** CONTOUR-BASED node detection — erase components (avg-color fill + binarize),
  contour-detect residual wire segments → nodes; channel-intersection for connectivity. == the
  B1/CC recipe we benchmark.
- **Validation:** automated LTspice DC operating-point match, topology-aware node matching
  (independent convergence with our SPICE sim_ok idea).
- **Results:** whole-netlist success rate — printed 93.33%, hand-drawn 85.33% (Table 8).
- **Comparability:** NOT directly comparable to ours (different dataset + metric: whole-netlist
  LTspice pass vs our component-pair F1 on CGHD). Added to paper related work + baseline framing:
  their contour node-detection is the prevailing recipe our endpoint-graph join (0.90) beats vs the
  CC baseline (0.61 on identical wires). Cite key: peker2026.
