# Iteration Tracker — Wire Detection FP Removal

## Status: IN PROGRESS

## Lead Priority Queue

| # | Lead | Status | Result | Notes |
|---|------|--------|--------|-------|
| 1 | Random Forest Classifier | ⏳ NEXT | — | Use 3 separable features |
| 2 | More feature engineering | 📋 QUEUED | — | Gradient, morphological, multi-scale |
| 3 | Wire endpoint refinement | 📋 QUEUED | — | Snap to edges using gradient |
| 4 | Iterative netlist refinement | 📋 QUEUED | — | Build → clean → re-detect → repeat |
| 5 | Component-type-specific rules | 📋 QUEUED | — | Different rules per component type |
| 6 | Pixel-level analysis | 📋 QUEUED | — | Analyze pixel patterns along wires |
| 7 | Morphological enhancement | 📋 QUEUED | — | Enhance wires before detection |
| 8 | Multi-scale detection | 📋 QUEUED | — | Detect at different scales |

## Completed Leads

| Lead | Result | F1 Impact | Verdict |
|------|--------|-----------|---------|
| Bbox connectivity | 88% removed are TPs | -0.060 | ❌ DEAD END |
| Per-component cap | Removes too many TPs | -0.154 | ❌ DEAD END |
| Static pin definitions | 29.8% connectivity | — | ❌ DEAD END |
| Simple confidence scoring | TP/FP identical | — | ❌ DEAD END |
| Endpoint clustering | 153.4% connectivity | — | ✅ USE FOR NETLIST |
| Multi-model consensus | P=0.9529, R=0.7063 | -0.022 | ⚠️ PRECISION ONLY |
| Topology validation | Removes 48 wires | -0.007 | ⚠️ GENTLE CLEANING |
| Deep feature exploration | 3 separable features | — | 🟡 LEAD FOUND |

## Dead End Criteria

A lead is DEAD END if:
- F1 drops by >0.02 AND no path to improvement
- All variants tested and none work
- Fundamental limitation identified

A lead is BLOCKED if:
- Requires data/tools not available
- Computationally infeasible
- Would take >1 hour to test

## Experiment Log

### 2026-05-31: Initial Exploration
- Tested bbox connectivity filtering → 88% TPs removed
- Tested per-component cap → too aggressive
- Tested static pin definitions → 29.8% connectivity

### 2026-05-31: Endpoint Clustering
- Implemented DBSCAN clustering
- Result: 153.4% connectivity (vs 29.8% static)
- Verdict: USE FOR NETLIST CONSTRUCTION

### 2026-05-31: Multi-Model Consensus
- Tested 4 detection methods
- TP detected by 4 methods: 68.9%
- FP detected by 4 methods: 17.9%
- Consensus (4 methods): P=0.9529, R=0.7063
- Verdict: PRECISION BOOST ONLY

### 2026-05-31: Topology Validation
- Built netlist, analyzed graph structure
- Floating components: 5572, dangling: 869, large: 48
- Degree≥10 threshold: removes 48 wires, F1=0.8263
- Verdict: GENTLE CLEANING

### 2026-05-31: Deep Feature Exploration
- Extracted 11 features per wire
- Found 3 separable features:
  - pixel_density: TP=0.14, FP=0.01
  - length: TP=65, FP=41
  - wire_width: TP=2.7, FP=0.3
- Ensemble scoring: removes 92% FPs, keeps 28% TPs
- Verdict: LEAD FOUND → try ML classifier

### NEXT: Random Forest Classifier
