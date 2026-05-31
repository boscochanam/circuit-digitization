# Autonomous Experimentation Log

## Started: 2026-05-31 (night session)
## Goal: Exhaustively test all approaches to improve wire detection F1 beyond 0.8334
## Status: IN PROGRESS

---

## Experiment Queue

### Priority 1: Image Preprocessing
- [ ] Test different thresholding methods (adaptive, Otsu, etc.)
- [ ] Test edge detection (Canny, Sobel)
- [ ] Test morphological operations (dilation, erosion)
- [ ] Test contrast enhancement (CLAHE, histogram equalization)

### Priority 2: Wire Detection Parameter Tuning
- [ ] Sweep Sauvola k parameter
- [ ] Sweep Sauvola window size
- [ ] Test different close kernel sizes
- [ ] Test different CCL min area

### Priority 3: Multi-Scale Detection
- [ ] Test different image resolutions
- [ ] Test different window sizes

### Priority 4: Ensemble Methods
- [ ] Combine different thresholding methods
- [ ] Combine different extraction methods

### Priority 5: Post-Processing Refinement
- [ ] Wire endpoint snapping to edges
- [ ] Wire merging for split wires
- [ ] Wire splitting for merged wires

### Priority 6: Advanced Features
- [ ] Texture features (LBP, GLCM)
- [ ] Shape features (curvature, complexity)
- [ ] Context features (surrounding pixels)

---

## Completed Experiments

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

### 2026-05-31: Random Forest v1
- Basic RF with 3 features (pixel_density, length, wire_width)
- Cross-validation F1: 0.9049
- Image-level F1: 0.8332 (Δ=-0.0002)
- Precision: 0.9872, Recall: 0.7208
- Verdict: REMOVES 90% FPs but also removes 7% TPs

### 2026-05-31: Random Forest v2 (OVERFITTING - INVALID)
- Extended RF with 7 features
- Cross-validation F1: 0.9483
- Image-level F1: 0.8750 (Δ=+0.0416)
- Precision: 1.0000, Recall: 0.7778
- TP: 2741 (unchanged), FP: 0 (all removed!)
- **INVALID: trained and tested on same data (overfitting)**

### 2026-05-31: Random Forest v3 (PROPER SPLIT)
- Train/test split by IMAGE (80/20)
- Cross-validation F1: 0.9500 (train set)
- Test set F1: 0.7845 (vs baseline 0.8334)
- Gap: 0.1655 (severe overfitting)
- Verdict: **DOES NOT IMPROVE F1 on unseen data**

### 2026-05-31: Simpler Models
- Logistic Regression: F1=0.5995 (worse)
- Decision Tree: F1=0.8512 (depth=10, may overfit)
- SVM: F1=0.6038 (worse)
- Rule 'length > 20': F1=0.8979 on one test set (appeared good)

### 2026-05-31: Rule Validation
- Tested "length > 20" across 10 random splits
- Average delta: -0.0542 ± 0.0122
- Positive: 0/10 splits
- Rule DOES NOT GENERALIZE (was split-specific artifact)
- All length thresholds reduce F1 on full dataset

---

## Current Status
- Baseline F1: 0.8334 (full dataset), 0.7852 (test set)
- Best result: 0.8334 (no improvement found)
- Next: Test wire detection parameter tuning

---

## 2026-05-31 23:50: Preprocessing Experiments
- Tested 7 preprocessing methods: none, clahe, histogram_eq, gaussian_blur, median_blur, bilateral, sharpen
- All methods reduce F1 on test set
- Best method: none (F1=0.7852)
- Close kernel=1: F1=0.7880 (marginal improvement)
- Sauvola k=0.285 is already optimal
- Verdict: **PREPROCESSING DOES NOT IMPROVE F1**

---

## Notes
- All experiments use proper train/test split by image (80/20)
- Cross-validation used for hyperparameter tuning
- Test set used for final evaluation only
- No data leakage between train and test sets
