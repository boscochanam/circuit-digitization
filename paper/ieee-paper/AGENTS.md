# IEEE Paper — Agent Instructions

## Paper Structure (Finalized)

**Title:** Degree-Budget Topology Join: Robust Wire-to-Component Connection for Scanned Circuit Diagram Digitization

**Authors:** Bosco, Chris Dcosta, Pranavesh Talupuri (USC)

### Paper Angle & Narrative

**Lead with:** Technical innovation (degree-budget join algorithm)
**Frame within:** Complete end-to-end system (scanned circuit → simulatable SPICE)
**Hint at:** Downstream application value (queryable circuits)

**NOT the main story:** LLM comparison — this is motivation only (1 paragraph + 1 figure in introduction)

### Section Structure

1. **Introduction** (1-2 pages)
   - Problem: scanned circuits are unstructured images
   - Gap: LLMs can describe but not digitize (show GPT-4V/Mimo failure example)
   - Our solution: CV pipeline → SPICE netlist
   - Key results: F1=0.976 wire detection, degree-budget handles 67% synthetic error
   - One paragraph + one figure comparing LLM vs pipeline (motivation, not contribution)

2. **Related Work** (1 page)
   - Circuit diagram understanding (Kelly & Cole, Kulkarni et al.)
   - Wire detection and joining (classical approaches)
   - Graph-based connectivity (union-find, GNNs)

3. **Pipeline Overview** (1-2 pages)
   - System architecture (6 stages)
   - Component detection (YOLO26M-OBB, 16 classes, 88.5% mAP50)
   - Wire extraction (Sauvola binarization, CCL, PCA endpoints)

4. **Degree-Budget Topology Join** (3-4 pages) ← **CORE CONTRIBUTION**
   - Endpoint-graph model (4 edge types)
   - Degree-budget completion (min-cost b-matching)
   - Self-loop guards and per-pin edge budget
   - Algorithm complexity and implementation details

5. **Evaluation** (2-3 pages)
   - Dataset: 134 images from CGHD-1152
   - Wire detection: F1=0.976
   - Join comparison: degree-budget (F1=0.94) vs baseline (F1=0.36)
   - Synthetic error injection framework (5 severity levels)
   - SPICE simulation validation (62% accurate currents under extreme noise)

6. **Conclusion + Future Work** (1 page)
   - Summary of contributions
   - Downstream applications (simulation, what-if analysis)
   - Future: handling crossovers, component value OCR

### Key Figures Needed

| Figure | Section | Description |
|--------|---------|-------------|
| Fig 1 | Intro | LLM vs Pipeline comparison (1 panel, motivation only) |
| Fig 2 | Intro/Method | Pipeline overview (6 stages) |
| Fig 3 | Method | Endpoint-graph model visualization |
| Fig 4 | Method | Degree-budget completion example |
| Fig 5 | Eval | F1 vs synthetic error severity |
| Fig 6 | Eval | Join comparison (our method vs baseline) |

### Key Numbers (Abstract)

- Wire detection F1: 0.976
- Degree-budget join F1: 0.94 (max error)
- Baseline join F1: 0.36 (max error)
- SPICE simulation accuracy: 62% (extreme noise)
- Dataset: 134 images, CGHD-1152

### LLM Comparison (Motivation Only)

- Model: Mimo 2.5 via OpenCode Go
- 10 test images, structured JSON prompt
- Result: LLM misses 26-67% of wires, error scales with complexity
- LLM produces unstructured JSON, not simulatable SPICE
- Use as motivation in introduction, not as main contribution

### Component Detection Model

- **Location:** `models/component_detection/yolo26m_obb_16class_aug.pt`
- **HuggingFace:** [boscochanam/circuit-component-detector](https://huggingface.co/boscochanam/circuit-component-detector)
- **Performance:** mAP50=88.5%, 16 classes
- **Dataset:** CGHD-1152 (Kaggle)

### File Locations

- Paper source: `paper.tex`
- Figures: `figures/`
- Pipeline code: `~/circuit-digitization/wire_detection/`
- Benchmark results: `~/circuit-digitization/wire_detection/benchmark/`

### Notes for Future Sessions

- LLM comparison data saved in `figures/llm_raw_v2/` (10 images, structured JSON)
- Pipeline SPICE files for comparison: `figures/C12_D2_P2_netlist_full.spice`, `figures/C128_D2_P4_netlist.spice`
- Paper structure decision: 2026-06-15
