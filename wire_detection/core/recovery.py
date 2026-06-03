"""Detection-recovery iterations for raw/HDC images.

The production detector (preset best_candidate_v4) loses wires on raw photos in
three ways documented in docs/hdc-detection-failures.md:
  A. faint strokes die at binarization (single global Sauvola, tuned for dark ink)
  B. the anchor filter over-deletes rails / junction wires
  C. the join under-connects (handled by the join-strategy registry, not here)

This module defines an ORDERED, CUMULATIVE list of fixes ("iterations") so a human
can step through them and see exactly which wires each one recovers (added) or
costs (removed). Each iteration is the previous one plus one change:

  0 baseline   — preset as-is
  1 contrast   — CLAHE local-contrast normalize (lifts faint pencil)
  2 faint      — gentler binarization: k 0.285->0.15, min_area 28->12, close 3->5
  3 grid       — FFT notch to suppress ruled/graph-paper grid (else #2 inflates FPs)
  4 anchor     — relax the anchor filter (endpoint 12->24, link 8->20): keep rails
  5 fusion     — vote Sauvola + Otsu (+CLAHE source) to catch strokes one method misses

The cfg overrides are applied on top of whatever ExperimentConfig the preset built,
so detection is otherwise identical. `grid_suppress` is image preprocessing applied
before detection when an iteration's `grid` flag is set.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Iteration:
    key: str
    label: str
    desc: str
    overrides: dict = field(default_factory=dict)
    grid: bool = False


# Cumulative — each row repeats the prior overrides plus its own change, so a config
# is fully described by its own row (no implicit ordering bugs).
_FAINT = {"normalize_mode": "clahe", "sauvola_k": 0.15, "ccl_min_area": 12, "close_kernel": 5}
_ANCHOR = {"anchor_endpoint_dist": 24.0, "anchor_link_dist": 20.0}
_FUSION = {
    "threshold_fusion_enabled": True,
    "threshold_vote": 1,                 # union: a pixel kept if ANY method fires
    "extra_threshold_methods": ("otsu",),
    "threshold_union_with_clahe": True,
}

ITERATIONS: list[Iteration] = [
    Iteration("baseline", "0 · Baseline", "Preset best_candidate_v4 as shipped (anchor 12/8, k0.285)."),
    Iteration("contrast", "1 · +Contrast", "CLAHE local-contrast normalize — lifts faint pencil strokes.",
              {"normalize_mode": "clahe"}),
    Iteration("faint", "2 · +Faint threshold", "Gentler binarization: k0.15, min_area12, close5.",
              dict(_FAINT)),
    Iteration("grid", "3 · +Grid suppress", "FFT-notch ruled/graph-paper grid so #2 doesn't trace it.",
              dict(_FAINT), grid=True),
    Iteration("anchor", "4 · +Junction anchor", "Relax anchor filter (endpoint24/link20) — keep rails & junctions.",
              {**_FAINT, **_ANCHOR}, grid=True),
    Iteration("fusion", "5 · +Threshold fusion", "Vote Sauvola+Otsu(+CLAHE) — catch strokes one method misses.",
              {**_FAINT, **_ANCHOR, **_FUSION}, grid=True),
]

DEFAULT_ITERATION = "anchor"


def list_iterations() -> list[dict]:
    return [{"key": it.key, "label": it.label, "desc": it.desc, "grid": it.grid} for it in ITERATIONS]


def get_iteration(key: str) -> Iteration:
    for it in ITERATIONS:
        if it.key == key:
            return it
    return ITERATIONS[0]


def grid_suppress(gray: np.ndarray, peak_pct: float = 99.6, protect_frac: float = 0.06) -> np.ndarray:
    """Suppress regular ruled/graph-paper grids via an FFT notch.

    A grid is a periodic pattern -> a regular lattice of sharp peaks in the 2-D
    spectrum. Real hand-drawn wires are aperiodic -> a smear through the origin.
    We zero the strongest peaks OUTSIDE a protected low-frequency disc (which holds
    the real structure + illumination), then invert. Plain paper has no strong
    periodic peaks, so this is ~a no-op there.
    """
    if gray.ndim != 2 or min(gray.shape) < 16:
        return gray
    g = gray.astype(np.float32)
    F = np.fft.fftshift(np.fft.fft2(g))
    mag = np.abs(F)
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rmin = protect_frac * min(h, w)
    thr = np.percentile(mag, peak_pct)
    notch = (mag > thr) & (r > rmin)
    F[notch] = 0.0
    out = np.fft.ifft2(np.fft.ifftshift(F)).real
    return np.clip(out, 0, 255).astype(np.uint8)


Line = tuple[tuple[int, int], tuple[int, int]]


def _line_dist(a: Line, b: Line) -> float:
    (a1, a2), (b1, b2) = a, b
    d_same = max(math.hypot(a1[0] - b1[0], a1[1] - b1[1]), math.hypot(a2[0] - b2[0], a2[1] - b2[1]))
    d_flip = max(math.hypot(a1[0] - b2[0], a1[1] - b2[1]), math.hypot(a2[0] - b1[0], a2[1] - b1[1]))
    return min(d_same, d_flip)


def diff_lines(cur: list[Line], prev: list[Line], tol: float = 14.0):
    """Classify cur vs prev: (added, kept, removed) by greedy endpoint matching."""
    used = [False] * len(prev)
    added: list[Line] = []
    kept: list[Line] = []
    for c in cur:
        best, bi = tol + 1.0, -1
        for i, p in enumerate(prev):
            if used[i]:
                continue
            d = _line_dist(c, p)
            if d < best:
                best, bi = d, i
        if bi >= 0 and best <= tol:
            used[bi] = True
            kept.append(c)
        else:
            added.append(c)
    removed = [p for i, p in enumerate(prev) if not used[i]]
    return added, kept, removed
