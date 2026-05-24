# Data Quality Guide

This document describes quality issues found in the CGHD1152 dataset and provides filtering strategies for selecting usable images.

## Quality Issues Identified

A 200-image random sample from CGHD1152 was analyzed using both programmatic metrics (brightness variance, FFT-based lined-paper detection, quadrant illumination variance) and vision model assessment (Qwen VL).

### Issue Prevalence

| Issue | Prevalence | Severity |
|---|---|---|
| Lined/graph paper background | **96%** | Medium — distracts wire detectors |
| Uneven lighting / shadows | **10%** | High — creates false wire edges |
| Phone photo capture | **majority** | Medium — perspective skew, blur |
| Severe underexposure (mean < 60) | **2%** | Critical — diagram invisible |
| Overexposure / glare (mean > 240) | **2%** | Critical — wire contrast lost |
| Clean images (no issues) | **2%** | N/A — rare |

### Affected Drafters

| Drafter | Primary Issue |
|---|---|
| drafter_27 | Strong blue color cast, very dark |
| drafter_25 | Overexposed, washed out |
| drafter_-1 | Grid paper + shadows |
| drafter_11 | Uneven quadrant illumination |
| drafter_29 | Hand/finger obstruction in frame |
| drafter_5, drafter_6 | Brown/corrugated paper + glare |

### Comparison: HDC Roboflow vs CGHD1152

| Property | HDC Roboflow | CGHD1152 |
|---|---|---|
| Capture method | Mixed (mostly cleaner) | Phone photos dominant |
| Background | Mostly clean/blank | 96% lined or grid |
| Lighting | Generally uniform | Frequent shadows |
| Image size | 704×704 (resized) | 1000×1000 (native) |
| Annotation format | YOLO OBB | PASCAL VOC XML |
| Drafters | Unknown | 33 known drafters |
| Augmentation | Flipped + rotated | None |

## Filtering Strategy

### Programmatic Quality Filters

```python
def quality_filter(image: np.ndarray) -> tuple[bool, list[str]]:
    """Returns (keep, issues) for a grayscale circuit image."""
    issues = []
    
    # 1. Brightness — reject extremes
    mean = np.mean(image)
    if mean < 60:  issues.append("too_dark")
    if mean > 240: issues.append("too_bright")
    
    # 2. Contrast — require minimum range
    contrast = (np.max(image) - np.min(image)) / 255
    if contrast < 0.16: issues.append("low_contrast")
    
    # 3. Lined paper — FFT horizontal frequency peaks
    h, w = image.shape
    strip = image[h//4:3*h//4, w//8:7*w//8]
    row_means = np.mean(strip, axis=1).astype(np.float32)
    row_means -= np.mean(row_means)
    row_means *= np.hanning(len(row_means))
    fft = np.abs(np.fft.rfft(row_means))
    fft /= np.mean(fft[1:]) + 1e-6
    if np.max(fft[3:30]) > 6.0:
        issues.append("lined_paper")
    
    # 4. Uneven lighting — quadrant variance
    q_means = [
        np.mean(image[:h//2, :w//2]),
        np.mean(image[:h//2, w//2:]),
        np.mean(image[h//2:, :w//2]),
        np.mean(image[h//2:, w//2:]),
    ]
    if np.std(q_means) > 30:
        issues.append("uneven_lighting")
    
    keep = len(issues) == 0 or (
        "too_dark" not in issues and
        "too_bright" not in issues and
        "low_contrast" not in issues
    )
    return keep, issues
```

### Recommended Filtering

| Strictness | Criteria | Approx. Yield | Use Case |
|---|---|---|---|
| **Lenient** | Exclude too_dark, too_bright, low_contrast | ~95% | Quick sweeps, development |
| **Moderate** | Also exclude uneven_lighting | ~85% | Evaluation benchmarks |
| **Strict** | Also exclude lined_paper | ~5% | Training data |

## Pre-processing Options

For images that pass lenient filtering but have background issues:

### Lined Paper Removal

```python
# FFT-based grid line removal
f = np.fft.fft2(image.astype(float))
fshift = np.fft.fftshift(f)
rows, cols = fshift.shape
# Mask the DC component region and horizontal frequency peaks
crow, ccol = rows // 2, cols // 2
mask = np.ones((rows, cols), dtype=bool)
mask[crow-3:crow+3, :] = 0  # horizontal DC band
fshift *= mask
result = np.abs(np.fft.ifft2(np.fft.ifftshift(fshift)))
```

### Lighting Normalization

```python
# CLAHE (Contrast Limited Adaptive Histogram Equalization)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
normalized = clahe.apply(image)
```

## Usage Recommendation

For the circuit digitization paper:

1. **Training**: Use HDC Roboflow data (already trained, known quality)
2. **Evaluation**: Use CGHD1152 with **moderate filtering** to test robustness across drafting styles
3. **Ablation**: Use CGHD drafter subsets to isolate style-specific failure modes
4. **Reporting**: Disclose quality filtering criteria and yields in the paper
