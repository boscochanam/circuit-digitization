# Nemotron VLM for Circuit Image Classification

## Objective

Use `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` via OpenRouter to classify circuit schematic images by **paper type** as part of the CGHD1152 dataset quality audit. Nemotron was chosen because it was the most capable free vision model available on OpenRouter at the time, with reasoning traces accessible via `include_reasoning=True`.

## Model Details

| Property | Value |
|----------|-------|
| Model | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Provider | OpenRouter (free tier) |
| Vision | Yes — accepts base64 images |
| Reasoning | Yes — `include_reasoning=True` surfaces chain-of-thought |
| Cost | Free (rate-limited) |

## Protocol

For each image in the CGHD1152 dataset sample (330 images across 33 drafters):

1. Load image, encode as base64 JPEG
2. Send to OpenRouter with:
   - Model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
   - Message: *"Describe this image in detail — what type of paper, lighting conditions, and visible content."*
   - `include_reasoning: true` — captured both the `content` (final description) and `reasoning` (chain-of-thought) fields
3. Parse VLM response to classify by paper type
4. Fall back to programmatic scores if VLM fails (truncated/empty/error response)

## Classification Schema

| Paper Type | Detection Method | Verdict |
|-----------|-----------------|---------|
| `plain_white` | "white paper", "plain white" | GOOD |
| `graph` | "graph paper", "grid paper", "grid pattern" | REJECT |
| `lined` | "lined paper", "ruled", "horizontal lines" | REJECT |
| `colored` | "blue paper", "colored paper" | MARGINAL |
| `textured` | "corrugated", "fabric", "rough texture" | REJECT |
| `dark` | "too dark", "underexposed" | REJECT |
| `glare` | "glare", "glossy", "reflection" | REJECT |
| `damaged` | "crumpled", "torn", "creased" | REJECT |
| `obstructed` | "thumb", "finger", "hand" | REJECT |

## Results (330 Images)

Nemotron produced descriptive responses averaging ~1,855 characters per image. The reasoning field provided chain-of-thought analysis that helped validate classification decisions.

### Verdict Distribution

| Verdict | Count |
|---------|-------|
| GOOD (plain white paper) | ~30-40% |
| REJECT (graph/lined/textured/etc.) | ~50-60% |
| MARGINAL (colored) | ~5-10% |
| NODATA (VLM failed → fallback) | ~5% |

### Programmatic Fallback

When nemotron returned an error (zip bomb, truncation, coordinate output), the system fell back to programmatic classification using:
- Mean brightness (dark if <60, overexposed if >240)
- Grid score (likely_grid if >35)
- Shadow score (shadow_issue if >40)
- Contrast ratio (low_contrast if <0.16)

## Key Files

| File | Description |
|------|-------------|
| `data/cghd_vlm_results.json` | Raw nemotron responses, 330 entries |
| `data/cghd_vlm_retry.json` | Retried entries for failed responses |
| `data/cghd_quality_sweep.json` | Programmatic quality scores per image |
| `data/cghd_reclassified.json` | Final classified output (paper type + verdict) |
| `data/cghd_final_audit.json` | Drafter-level quality audit |
| `reclassify_images.py` | Original classification script with VLM + programmatic fallback |
| `generate_audit.py` | Original drafter-level audit script |
| `generate_audit_pdf.py` | PDF report generator |
| `send_pranavesh_audit.py` | Email script sending the full audit report |

*Note: All files above are inside the `docs/experiments/` directory. The same logic is also available as a reusable Python module at `wire_detection/vlm/vlm_classifier.py` with a `wire-vlm` CLI.*

## Reusable Module

The classification logic has been refactored into `wire_detection.vlm` for use in the pipeline:

```bash
# Classify a single image (VLM + programmatic)
wire-vlm classify image.jpg

# Sweep a directory (programmatic only, no API calls)
wire-vlm sweep ./images/ --output sweep.json

# Full audit pipeline from saved VLM results
wire-vlm audit-pipeline --results-dir docs/experiments/data/
```

## Verdict

Nemotron's free tier was adequate for this task — it produced useful descriptive responses for ~95% of images. The reasoning traces (`include_reasoning=True`) were a distinguishing advantage over GPT-4o-mini and Qwen2.5-VL, making classification decisions more auditable. The programmatic fallback handled the remaining ~5% where the VLM returned errors or truncated output.
