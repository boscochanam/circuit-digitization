"""
VLM (Vision Language Model) Classifier for circuit schematic images.

Uses OpenRouter API to call vision models (Nemotron, Qwen, etc.) for
paper-type classification and quality assessment of circuit diagram images.

Designed for further experimentation — swap the model, prompt, or
classification schema without touching the core pipeline.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# ── Schema ────────────────────────────────────────────────────────

PAPER_TYPE_PATTERNS: dict[str, list[str]] = {
    "graph": [
        "graph paper",
        "grid paper",
        "fine gray grid",
        "grid of small black dots",
        "regular grid",
        "dot grid",
        "light grid",
        "graph-paper",
        "blue grid",
        "grid pattern",
        "grid of fine lines",
        "grid of dots",
        "background grid",
        "gray grid lines",
        "white grid",
        "blue-tinted graph",
        "light blue grid",
        "grid-patterned",
        "subtle light grid",
        "blue grid-patterned",
        "light grid pattern",
        "grid background",
        "white graph paper",
        "blue graph paper",
    ],
    "lined": [
        "lined paper",
        "ruled paper",
        "horizontal lines",
        "notebook paper",
        "writing lines",
        "college ruled",
        "wide ruled",
        "lined notebook",
        "ruled notebook",
        "composition notebook",
        "blue vertical lines",
        "light blue horizontal lines",
        "red vertical lines",
        "lined sheet",
        "ruled sheet",
        "vertical blue lines",
        "blue ruled",
        "red margin",
        "ruled paper",
        "lined page",
        "blue horizontal lines",
        "horizontal blue lines",
        "vertically lined",
        "vertically ruled",
    ],
    "colored": [
        "blue paper",
        "blue surface",
        "solid blue",
        "vibrant blue",
        "pink paper",
        "green paper",
        "colored paper",
        "light blue paper",
        "blue background",
        "light blue surface",
        "pale blue",
        "light blue",
        "blue-tinted",
    ],
    "textured": [
        "corrugated",
        "fabric",
        "carpet",
        "wooden surface",
        "rough texture",
        "cardboard",
        "orange peel",
        "textured surface",
        "cloth",
        "orange paper",
        "yellow paper",
        "solid grey background",
        "grey background",
        "gray textured",
        "light gray textured",
        "vertical ridges",
        "corrugated appearance",
        "whiteboard",
        "whiteboard or similar",
        "gray textured paper",
    ],
    "glare": ["glare", "glossy", "reflection", "shiny"],
    "damaged": [
        "crumpled",
        "wrinkled",
        "creased",
        "curling up",
        "torn",
        "folded",
        "curling",
        "bent corner",
    ],
    "dark": [
        "too dark",
        "very dark",
        "underexposed",
        "barely visible",
        "poor lighting",
        "extremely dark",
    ],
    "obstructed": [
        "thumb",
        "finger",
        "fingers",
        "hand holding",
        "hand visible",
        "person holding",
        "shadow of a hand",
        "hand obstruct",
        "hand casting",
        "hand at the",
        "hand in the",
        "finger at the",
        "fingertip",
        "palm",
        "hand covering",
    ],
    "plain_white": [
        "white paper",
        "white background",
        "white surface",
        "plain paper",
        "plain white",
        "clean white",
        "sheet of white paper",
        "white sheet",
        "plain white paper",
        "white piece of paper",
        "off-white paper",
        "white page",
        "white notebook paper",
        "white, plain paper",
    ],
}

REJECT_TYPES = {
    "graph",
    "lined",
    "textured",
    "damaged",
    "obstructed",
    "glare",
    "dark",
    "likely_grid",
    "shadow_issue",
}

DEFAULT_PROMPT = (
    'Describe this image in as much detail as possible. Include:\n'
    '- What is the subject?\n'
    '- What does the background/surface look like? Describe its color, texture, any patterns.\n'
    '- How would you characterize the lighting? Is it bright, dim, even, uneven? Are there shadows?\n'
    '- What is the overall contrast like?\n'
    '- How does the image quality strike you — is it sharp or blurry? Clean or noisy?\n'
    '- Any notable artifacts, reflections, or obstructions?\n'
    '\n'
    'Do NOT categorize or label anything — just describe what you see.'
)


# ── Data classes ──────────────────────────────────────────────────


@dataclass
class ClassificationResult:
    path: str
    drafter: str
    filename: str
    paper_type: str
    reason: str
    grid_score: float
    mean_brightness: float
    shadow_score: float
    verdict: str


@dataclass
class ProgrammaticScore:
    mean: float = 128.0
    contrast: float = 0.5
    grid_score: float = 0.0
    shadow_score: float = 0.0
    composite: float = 0.5
    stratum: str = "middle"


# ── VLM API ───────────────────────────────────────────────────────


class OpenRouterVLM:
    """Call vision models via OpenRouter API.

    Requires OPENROUTER_API_KEY env var or an OpenRouter config file.
    """

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        api_key: str | None = None,
        include_reasoning: bool = True,
        max_retries: int = 3,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.include_reasoning = include_reasoning
        self.max_retries = max_retries

    def classify_image(self, image_path: str | Path, prompt: str = DEFAULT_PROMPT) -> str:
        """Send an image to the VLM and return the text response."""

        import urllib.request

        image_path = Path(image_path)
        if not image_path.exists():
            return f"ERROR: image not found: {image_path}"

        # Encode image as base64 JPEG
        img = cv2.imread(str(image_path))
        if img is None:
            return f"ERROR: could not decode image: {image_path}"
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64 = base64.b64encode(buf).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }

        if self.include_reasoning:
            payload["include_reasoning"] = True

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.BASE_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/boscochanam/circuit-digitization",
            },
            method="POST",
        )

        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode())
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                content = msg.get("content", "") or ""
                reasoning = msg.get("reasoning", "") or ""
                if self.include_reasoning and reasoning.strip():
                    content = f"{content}\n\n[REASONING]\n{reasoning}"
                return content.strip() or "ERROR: empty response"
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                else:
                    return f"ERROR: {e}"


# ── Classification helpers ────────────────────────────────────────


def classify_vlm_response(resp: str) -> tuple[str, str]:
    """Determine paper type and reason from a VLM response string."""
    lower = resp.lower()
    if len(resp) < 10 or resp.strip() in ("The", "So", ""):
        return ("vlm_failed", "truncated")
    if resp.startswith("ERROR:"):
        return ("vlm_failed", resp[:50])
    if "<point>" in resp or '"bbox_2d"' in resp:
        return ("vlm_failed", "coordinate_output")

    for paper_type, patterns in PAPER_TYPE_PATTERNS.items():
        for p in patterns:
            if p in lower:
                return (paper_type, p)

    # Fuzzy fallbacks
    if "grid" in lower and any(w in lower for w in ["paper", "background", "surface"]):
        return ("graph", "fuzzy_grid")
    if "graph" in lower:
        return ("graph", "fuzzy_graph")
    if "paper" in lower and "textured" in lower:
        return ("textured", "textured_paper")
    if "whiteboard" in lower:
        return ("textured", "whiteboard")
    return ("unclear", "no_pattern_match")


def classify_programmatic(score: ProgrammaticScore) -> tuple[str, str]:
    """Fallback classification from programmatic image scores."""
    if score.mean < 60:
        return ("dark", "programmatic_too_dark")
    if score.mean > 240:
        return ("glare", "programmatic_overexposed")
    if score.contrast < 0.16:
        return ("dark", "programmatic_low_contrast")
    if score.grid_score > 35:
        return ("likely_grid", f"programmatic_grid_{score.grid_score:.0f}")
    if score.shadow_score > 40:
        return ("shadow_issue", f"programmatic_shadow_{score.shadow_score:.0f}")
    return ("unknown", "programmatic_no_issue")


def get_verdict(paper_type: str) -> str:
    """Map paper type to verdict: GOOD / MARGINAL / REJECT / NODATA."""
    if paper_type in REJECT_TYPES:
        return "REJECT"
    if paper_type == "colored":
        return "MARGINAL"
    if paper_type == "plain_white":
        return "GOOD"
    return "NODATA"


# ── Programmatic quality scoring ──────────────────────────────────


def compute_quality_scores(
    image: np.ndarray,
    grid_fft_threshold: float = 6.0,
    shadow_std_threshold: float = 30.0,
) -> ProgrammaticScore:
    """Compute programmatic quality metrics for a grayscale image."""
    h, w = image.shape
    mean = float(np.mean(image))
    contrast = float((np.max(image) - np.min(image)) / 255.0)

    # Grid score via FFT on horizontal strip
    strip = image[h // 4 : 3 * h // 4, w // 8 : 7 * w // 8]
    row_means = np.mean(strip, axis=1).astype(np.float32)
    row_means -= np.mean(row_means)
    row_means *= np.hanning(len(row_means))
    fft = np.abs(np.fft.rfft(row_means))
    fft_ratio = float(np.max(fft[3:30]) / (np.mean(fft[1:]) + 1e-6))
    grid_score = max(0.0, fft_ratio)

    # Shadow score via quadrant std
    q_means = [
        np.mean(image[: h // 2, : w // 2]),
        np.mean(image[: h // 2, w // 2 :]),
        np.mean(image[h // 2 :, : w // 2]),
        np.mean(image[h // 2 :, w // 2 :]),
    ]
    shadow_score = max(0.0, float(np.std(q_means)))

    # Composite (higher = better)
    brightness_ok = 1.0 if 60 < mean < 240 else 0.0
    grid_ok = max(0.0, 1.0 - grid_score / 50.0)
    shadow_ok = max(0.0, 1.0 - shadow_score / 50.0)
    composite = (brightness_ok * 0.3 + grid_ok * 0.4 + shadow_ok * 0.3)

    # Stratum for stratified sampling
    if composite > 0.75:
        stratum = "top"
    elif composite > 0.55:
        stratum = "middle"
    else:
        stratum = "bottom"

    return ProgrammaticScore(
        mean=mean,
        contrast=contrast,
        grid_score=grid_score,
        shadow_score=shadow_score,
        composite=composite,
        stratum=stratum,
    )


# ── Batch processing ──────────────────────────────────────────────


def reclassify_dataset(
    vlm_results: list[dict[str, Any]],
    sweep_results: list[dict[str, Any]],
    use_vlm_fallback: bool = True,
) -> list[ClassificationResult]:
    """Reclassify images by paper type from VLM responses + programmatic fallback."""
    from collections import Counter

    # Build path-based lookup
    path_map: dict[str, dict] = {}
    for entry in vlm_results:
        path_map[entry["path"]] = entry
    sweep_map: dict[str, dict] = {e["path"]: e for e in sweep_results}

    results: list[ClassificationResult] = []
    for path, entry in path_map.items():
        resp = (entry.get("vlm_response") or "").strip()
        resp_lower = resp.lower()
        prog = sweep_map.get(path, {})

        paper_type, reason = classify_vlm_response(resp_lower)

        # VLM failed → programmatic fallback
        if paper_type == "vlm_failed" and use_vlm_fallback:
            prog_score = ProgrammaticScore(
                mean=prog.get("mean", 128),
                contrast=prog.get("contrast", 0.5),
                grid_score=prog.get("grid_score", 0),
                shadow_score=prog.get("shadow_score", 0),
            )
            paper_type, reason = classify_programmatic(prog_score)

        verdict = get_verdict(paper_type)
        results.append(
            ClassificationResult(
                path=path,
                drafter=entry.get("drafter", ""),
                filename=entry.get("filename", ""),
                paper_type=paper_type,
                reason=reason,
                grid_score=prog.get("grid_score", 0),
                mean_brightness=prog.get("mean", 128),
                shadow_score=prog.get("shadow_score", 0),
                verdict=verdict,
            )
        )

    return results


def classify_image_direct(
    image_path: str | Path,
    vlm: OpenRouterVLM | None = None,
    prompt: str = DEFAULT_PROMPT,
) -> ClassificationResult:
    """Classify a single image directly: VLM call + programmatic fallback."""
    import re

    image_path = Path(image_path)
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return ClassificationResult(
            path=str(image_path), drafter="", filename=image_path.name,
            paper_type="error", reason="could_not_read", grid_score=0,
            mean_brightness=0, shadow_score=0, verdict="NODATA",
        )

    prog_score = compute_quality_scores(gray)

    if vlm is not None:
        resp = vlm.classify_image(image_path, prompt)
        paper_type, reason = classify_vlm_response(resp.lower())
        if paper_type == "vlm_failed":
            paper_type, reason = classify_programmatic(prog_score)
    else:
        paper_type, reason = classify_programmatic(prog_score)

    verdict = get_verdict(paper_type)
    return ClassificationResult(
        path=str(image_path),
        drafter=re.sub(r"/images/.*", "", str(image_path)).split("/")[-1] if "/" in str(image_path) else "",
        filename=image_path.name,
        paper_type=paper_type,
        reason=reason,
        grid_score=prog_score.grid_score,
        mean_brightness=prog_score.mean,
        shadow_score=prog_score.shadow_score,
        verdict=verdict,
    )
