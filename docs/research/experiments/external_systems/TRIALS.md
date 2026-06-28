# External-system reproduction trials (2026-06-28)

Goal: attempt to run prior image→netlist systems on our hand-drawn verified-GT images and,
where possible, compare connectivity. Honest log; flag REAL blockers and move on. Clones in
scratchpad (ephemeral); commands here for reproducibility.

## Outcome table
| System | Repo | Status | Real blocker / finding |
|--------|------|--------|------------------------|
| Kelly & Cole (CircuitSchematicImageInterpreter) | github.com/C-R-Kelly/... | RAN, fails on hand-drawn | Classical printed-schematic interpreter (Hough axis-aligned wire scan). Installs+runs cleanly on its own printed test image (12 comps, graph 9 nodes/12 edges). On our hand-drawn scans it over-segments wires into 26–53 spurious "components" (vs 4–12 real) and recovers ~0 connectivity (graph edges 0–4). Domain-transfer failure, not a code bug. Cannot be fairly scored vs our GT. |
| Masala-CHAI / Auto-SPICE | github.com/jitendra-bhandari/Masala-CHAI | BLOCKED | Connectivity/netlist is produced BY an LLM (OpenAI GPT-4/5 via `run_gpt`, needs a paid API key); the YOLO+Hough parts only feed the prompt. So it is an LLM-does-the-netlist method — redundant with our own VLM experiment (Claude) — and requires paid API + printed-textbook domain. Not a deterministic algorithm to run offline. |
| CircuitNet | github.com/aaanthonyyy/CircuitNet | BLOCKED | Repo is 4 Colab notebooks (`*.ipynb`), 0 standalone `.py`, no trained weights included; netlist step is a "proprietary generation algorithm." Not headless-runnable / not reproducible as-is. |
| Netlistify (NVIDIA/NYCU, MLCAD'25) | github.com/NYCU-AI-EDA/Netlistify | REPRODUCED on own data; NOT applicable to hand-drawn | Learned Transformer (DETR-style) connectivity. Weights via README Drive link (687MB zip = all 3 files inference.py needs). Set up in a venv (torch 2.12+cu130; had to disable cuDNN for a Blackwell sublibrary-version-mismatch). Successfully ran inference.py end-to-end on its OWN printed-AMS test images → produced valid .sp netlists (61 outputs). BUT (real blocker) it cannot be fairly applied to our benchmark: the active model's class taxonomy is [gnd,pmos,nmos,pnp,npn,resistor,capacity,voltage,current,text,node,crossing] — NO diode/inductor/IC classes, which most of our CGHD circuits contain — and the connectivity model is trained on PRINTED thin-line appearance, not hand-drawn pencil. Force-mapping our components would be semantically wrong, so we report it as reproduced-but-not-transferable, not a fabricated score. |
| SINA | anonymous.4open.science/r/SINA-213F | BLOCKED | Anonymous peer-review archive; the 4open.science zip API returned truncated/unextractable downloads on repeated attempts (BadZipFile). Connectivity = connected-component labeling, already represented by our CC baseline (0.61 on identical detected wires). Not pursued further. |

## Key takeaway (so far)
The reproducible, deterministic prior connectivity methods are classical (CCL/contour: SINA,
Peker, AMSnet, Bayer; Hough: Reddy&Panicker; printed interpreter: Kelly) — all either tested by
us as baselines on identical input (CCL 0.61, Hough 0.85 vs ours 0.90) or shown not to transfer
to hand-drawn (Kelly). Learned methods (Netlistify) and LLM methods (Masala-CHAI) are trained on
PRINTED schematics / need paid APIs → not fairly runnable on hand-drawn CGHD without retraining.
This is itself the finding: no prior system provides a deterministic, hand-drawn-ready connectivity
module we can drop onto our benchmark — reinforcing the contribution of our verified net-GT +
endpoint-graph join.
