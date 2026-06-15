# Circuit Digitization Pipeline — Exhaustive Testing & Evaluation Checklist

**Created:** 2026-06-16 00:30
**Deadline:** 2026-06-16 09:00
**Branch:** `feature/exhaustive-testing`

---

## Phase 1: Core Pipeline Components

### 1.1 Component Detection (YOLO26M-OBB)
- [ ] Model loads correctly from `models/component_detection/yolo26m_obb_16class_aug.pt`
- [ ] ONNX export works (if attempted)
- [ ] Inference produces correct class IDs (16 classes)
- [ ] Bounding boxes are accurate (OBB format)
- [ ] Confidence scores are reasonable (>0.5 for most detections)
- [ ] All 16 classes are detected: resistor, capacitor-polarized, capacitor-unpolarized, capacitor-adjustable, inductor, inductor-ferrite, diode, diode-LED, diode-zener, diode-thyrector, fuse, lamp, switch, varistor, relay, transformer, motor, microphone, probe, transistor-BJT, transistor-FET, opamp, opamp-schmitt, IC, IC-NE555, IC-voltage-reg, junction, terminal, gnd, crossover, text, other
- [ ] Component detection handles rotated images
- [ ] Component detection handles noisy/scanned images
- [ ] Performance: <2s per image on CPU

### 1.2 Component Occlusion
- [ ] Local median fill works correctly
- [ ] Margin calculation: 15% of bbox size, min 5px
- [ ] Occlusion doesn't bleed outside component boundaries
- [ ] Text labels are properly occluded
- [ ] Junction points are preserved (not occluded)

### 1.3 ROI Crop + Padding
- [ ] Crop bounds are correct (union of component bboxes + 10px padding)
- [ ] Offset tracking is correct (rx1, ry1)
- [ ] Component coordinates are properly shifted
- [ ] Edge cases: components at image boundaries
- [ ] Edge cases: single component images

### 1.4 Sauvola Binarization
- [ ] k=0.285 parameter is applied correctly
- [ ] Window size=67 is applied correctly
- [ ] Binary output is clean (minimal noise)
- [ ] Thin wires are preserved
- [ ] Thick wires are preserved
- [ ] Junctions are preserved

### 1.5 Morphological Close
- [ ] Ellipse 3×3 kernel is applied
- [ ] Small gaps in wires are filled
- [ ] Wire endpoints are not distorted
- [ ] Junction geometry is preserved

### 1.6 Connected Component Labeling (CCL)
- [ ] min_area=28 filter works correctly
- [ ] Small noise components are removed
- [ ] Large components are preserved
- [ ] Component count is reasonable

### 1.7 Wire Endpoint Extraction (PCA)
- [ ] PCA endpoints are computed correctly
- [ ] Endpoint positions are accurate
- [ ] Multiple endpoints per wire are handled
- [ ] Collinear fragments are detected

### 1.8 Overlap Deduplication
- [ ] angle=12° threshold works correctly
- [ ] dist=18px threshold works correctly
- [ ] Duplicate wires are removed
- [ ] Unique wires are preserved
- [ ] T-junctions are handled correctly

### 1.9 Anchor Filter
- [ ] endpoint_dist=16 threshold works correctly
- [ ] link_dist=8 threshold works correctly
- [ ] Unconnected endpoints are filtered
- [ ] Connected endpoints are preserved

---

## Phase 2: Join Strategy (Degree-Budget Topology Join)

### 2.1 Endpoint-Graph Construction
- [ ] Wire body edges are created (type 1)
- [ ] Endpoint-endpoint edges are created (type 2)
- [ ] Endpoint-pin edges are created (type 3)
- [ ] T-junction edges are created (type 4)
- [ ] Edge weights are computed correctly

### 2.2 Pin Discovery
- [ ] Component pins are derived from OBB geometry
- [ ] 2-terminal components have correct pin count
- [ ] 3-terminal components (transistors) have correct pin count
- [ ] 4-terminal components (opamps) have correct pin count
- [ ] Pin positions are accurate

### 2.3 Degree-Budget Completion
- [ ] Min-cost b-matching works correctly
- [ ] Per-pin edge budget is enforced
- [ ] Self-loop guards prevent shorts
- [ ] Dropped connections are recovered
- [ ] Over-merge is prevented

### 2.4 Netlist Generation
- [ ] Nodes are created correctly
- [ ] Pins are assigned to nodes
- [ ] Wires are assigned to nodes
- [ ] Component types are tracked

---

## Phase 3: SPICE Netlist Generation

### 3.1 SpiceGenerator
- [ ] Component types map to SPICE prefixes (R, C, L, D, Q, V, U)
- [ ] Reference designators are generated correctly
- [ ] Pin nodes are assigned correctly
- [ ] GND node is identified correctly
- [ ] Net names are generated (N0, N1, etc.)

### 3.2 Netlist Format
- [ ] SPICE header is correct
- [ ] Component lines are well-formed
- [ ] .end directive is present
- [ ] Values are placeholder (1k, 100n, etc.)
- [ ] Analysis directives are included (.ac, .tran)

### 3.3 Netlist Validation
- [ ] All components have exactly 2 pins (except transistors, opamps)
- [ ] All nets are referenced
- [ ] No floating nodes
- [ ] GND is connected

---

## Phase 4: Evaluation Metrics

### 4.1 Wire Detection Metrics
- [ ] True Positives (TP) are counted correctly
- [ ] False Positives (FP) are counted correctly
- [ ] False Negatives (FN) are counted correctly
- [ ] Precision = TP / (TP + FP)
- [ ] Recall = TP / (TP + FN)
- [ ] F1 = 2 * P * R / (P + R)
- [ ] Exact-match label comparison works

### 4.2 Join Metrics
- [ ] Connection accuracy is measured
- [ ] Net assignment accuracy is measured
- [ ] Over-merge rate is measured
- [ ] Under-merge rate is measured

### 4.3 Synthetic Error Injection
- [ ] Error levels L0-L5 work correctly
- [ ] Endpoint displacement is realistic
- [ ] Wire dropping is realistic
- [ ] Error severity is controllable

### 4.4 SPICE Simulation Validation
- [ ] ngspice integration works
- [ ] DC analysis produces correct results
- [ ] AC analysis produces correct results
- [ ] Current measurements are accurate

---

## Phase 5: Benchmark Dataset

### 5.1 Dataset Integrity
- [ ] 134 benchmark images exist
- [ ] Ground truth wire labels exist for all images
- [ ] Component labels exist for all images
- [ ] Image filenames match label filenames

### 5.2 Config Comparison
- [ ] a16 config (best) produces F1=0.9755
- [ ] v4 baseline produces F1=0.9730
- [ ] Other configs produce expected results
- [ ] Per-image breakdown matches expected distribution

### 5.3 Cross-Drafter Generalization
- [ ] Model works on drafter_0 (if included)
- [ ] Model works on drafter_1
- [ ] Model works on drafter_2
- [ ] Model works on drafter_3

---

## Phase 6: Code Quality & Consistency

### 6.1 Import Paths
- [ ] All imports resolve correctly
- [ ] No circular dependencies
- [ ] No missing modules

### 6.2 Configuration
- [ ] Default config loads correctly
- [ ] Custom configs override correctly
- [ ] Config validation works

### 6.3 Error Handling
- [ ] Missing images are handled gracefully
- [ ] Missing labels are handled gracefully
- [ ] Empty detection results are handled
- [ ] Pipeline failures produce meaningful errors

### 6.4 API Routes
- [ ] /process endpoint works
- [ ] /netlist endpoint works
- [ ] /simulate endpoint works
- [ ] /join_overlay endpoint works
- [ ] /current_overlay endpoint works

---

## Phase 7: Paper Figure Generation

### 7.1 Pipeline Overview Figure
- [ ] 6-stage pipeline visualization is correct
- [ ] Arrows and labels are accurate
- [ ] Resolution is high enough (2x+)

### 7.2 LLM vs Pipeline Comparison
- [ ] LLM results are documented
- [ ] Pipeline results are documented
- [ ] Comparison table is accurate
- [ ] Figure is ready for paper

### 7.3 Per-Image Examples
- [ ] C84_D2_P1 (dense, 42 wires) is ready
- [ ] C29_D2_P4 (medium, 26 wires) is ready
- [ ] C34_D1_P1 (simple, 19 wires) is ready
- [ ] C63_D2_P3 (max complexity, 72 wires) is ready

### 7.4 Evaluation Figures
- [ ] F1 vs error severity plot is ready
- [ ] Join comparison plot is ready
- [ ] Per-circuit performance table is ready

---

## Phase 8: Documentation

### 8.1 Code Documentation
- [ ] All functions have docstrings
- [ ] Complex algorithms are documented
- [ ] Configuration options are documented

### 8.2 Paper Documentation
- [ ] Abstract is complete
- [ ] Introduction is complete
- [ ] Related work is complete
- [ ] Method section is complete
- [ ] Evaluation section is complete
- [ ] Conclusion is complete

### 8.3 AGENTS.md
- [ ] Paper structure is documented
- [ ] Key numbers are documented
- [ ] File locations are documented
- [ ] LLM comparison notes are documented

---

## Phase 9: Deployment & Reproducibility

### 9.1 Environment
- [ ] Python version is specified (3.13+)
- [ ] Dependencies are listed in pyproject.toml
- [ ] Virtual environment can be created from scratch
- [ ] Model weights can be downloaded

### 9.2 Scripts
- [ ] Benchmark script runs end-to-end
- [ ] Pipeline examples script runs end-to-end
- [ ] Evaluation script runs end-to-end

### 9.3 Git
- [ ] All changes are committed
- [ ] No sensitive data in repo
- [ ] .gitignore is correct

---

## Phase 10: Final Validation

### 10.1 Full Pipeline Test
- [ ] Run pipeline on 10 test images
- [ ] Verify SPICE netlists are generated
- [ ] Verify netlists simulate correctly
- [ ] Compare with LLM output

### 10.2 Benchmark Validation
- [ ] Run expanded benchmark on 134 images
- [ ] Verify F1=0.9755 for a16 config
- [ ] Verify per-image breakdown matches

### 10.3 Paper Readiness
- [ ] All figures are generated
- [ ] All tables are complete
- [ ] All references are cited
- [ ] LaTeX compiles without errors

---

## Progress Log

| Time | Item | Status | Notes |
|------|------|--------|-------|
| | | | |
