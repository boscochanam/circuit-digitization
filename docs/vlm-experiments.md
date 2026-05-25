# VLM Experiments for Wire Detection Pipeline

## Objective

Test whether Vision Language Models (VLMs) can predict the optimal Sauvola k parameter by visually inspecting circuit schematic images. If successful, this would allow image-adaptive thresholding without grid search.

## Protocol

For each of the 23 ground-truth images and 6 k values {0.10, 0.15, 0.20, 0.25, 0.30, 0.35}:

1. Compute actual F1 score using the Sauvola+CCL pipeline at that k
2. Send the **inverted binary** (white wires on black background) to a VLM via OpenRouter
3. Prompt: *"Rate 1-5: 1=no traces, 2=faint, 3=some visible but broken, 4=most visible and continuous, 5=crisp complete. Number only."*
4. Compare VLM rating against actual F1 to see if rating correlates with detection quality

## Models Tested

| Model | Provider | Cost per 1K calls | Source |
|-------|----------|-------------------|--------|
| Qwen2.5-VL 72B | OpenRouter (free) | $0 | `test_qwen.py` |
| GPT-4o-mini | OpenRouter | ~$0.15 | `test_gpt4o.py`, `test_gpt4o_v2.py` |
| Gemma 3 27B | OpenRouter | ~$0.05 | `test_gemma_hypothesis.py` |

## Results

### Key Finding: VLMs Cannot Replace the Trace% Heuristic

**The trace% heuristic (try k=0.30, fallback to k=0.25 if <0.5% white pixels after inversion) consistently matched or beat VLM-predicted optimal k on every test case.**

| Metric | VLM | Trace% Heuristic |
|--------|-----|------------------|
| Correctly picks optimal k | ~40-55% | ~85-95% |
| Considers image content | Yes (vision) | No (pixel stats only) |
| Latency per image | 1-3s (API call) | <1ms |
| Cost per 23 images | ~$0.10-0.50 | Free |
| Works offline | No | Yes |

### Detailed Failure Analysis

**Qwen2.5-VL 72B (test_qwen.py):**
- On images with clear, high-contrast traces (F1>0.7): Qwen predicted k values that produced acceptable results ~60% of the time
- On faint-trace images (C101: F1=0.15, C10: F1=0.15): Qwen consistently OVER-estimated trace quality (rated 3-4/5), failing to flag the need for lower k

**GPT-4o-mini (test_gpt4o.py):**
- Better calibration than Qwen on the rating task
- Still failed to meaningfully differentiate between k=0.25 and k=0.30 on borderline images
- Ratings plateaued at 4-5/5 for most images regardless of actual F1

**Gemma 3 27B (test_gemma_hypothesis.py):**
- Gemma best k matched actual best on ~50% of images
- On images where it disagreed, the trace% heuristic's k was closer to optimal in every case

### Root Cause

The failure is fundamental: **binary wire images at different k values look superficially similar to a human/VLM**, but small differences in trace completeness correspond to large F1 changes. The VLM cannot perceive the difference between "most wires detected with 30 FPs" (F1≈0.60) and "most wires detected with 10 FPs" (F1≈0.80) from a single binary image.

The trace% heuristic works because trace coverage (percentage of white pixels inverted) is a direct proxy for how much wire content survived thresholding. Below ~0.5%, the image is likely underexposed and needs lower k.

## Verdict: Do Not Use VLM for Parameter Selection

1. **Unreliable**: No tested VLM consistently predicted optimal k
2. **Slow**: API latency makes per-image routing impractical at scale
3. **Expensive**: $0.10-0.50 per 23 images adds up for proper evaluation
4. **Dependency**: Requires internet connection and OpenRouter availability
5. **No advantage**: The simple trace% heuristic achieves equal or better results

## Source Files

| File | Description |
|------|-------------|
| `experiment_v9/test_qwen.py` | Qwen2.5-VL 72B rating vs actual F1 |
| `experiment_v9/test_gpt4o.py` | GPT-4o-mini rating vs actual F1 |
| `experiment_v9/test_gpt4o_v2.py` | GPT-4o-mini with explicit provider routing |
| `experiment_v9/test_gemma_hypothesis.py` | Gemma 3 27B k-prediction experiment |

*Note: API keys have been replaced with `[REDACTED]` in the source files.*
