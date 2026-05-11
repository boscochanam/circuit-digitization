# Pipeline Stages

## Crop

Crop the image to a region of interest defined by component bounding boxes.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `padding` | int | 10 | Extra pixels around the bbox |

Reads component OBB labels from the corresponding label file, computes the min/max bounds, and crops with padding.

## Mask

Fill annotated component polygons with white to occlude wires that pass behind components.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `fill_value` | int | 255 | Grayscale value for fill |

Only applies when component labels are available. Without component labels, this is a no-op.

## Threshold

Convert grayscale image to binary.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | str | `otsu` | `otsu`, `manual`, or `adaptive` |
| `value` | int | 127 | Threshold value (for `manual` mode) |
| `block_size` | int | 31 | Block size (for `adaptive` mode) |
| `c` | int | 2 | Constant subtracted from mean (for `adaptive` mode) |

**Otsu** automatically determines the optimal threshold. **Manual** uses a fixed value. **Adaptive** computes per-pixel thresholds using the mean of a block neighborhood.

## Invert

Bitwise NOT — flips black to white and vice versa. After thresholding, wires are typically black; this stage makes them white for subsequent processing.

No parameters.

## Dilate

Morphological dilation to thicken thin wire segments, making them easier to detect.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `kernel_size` | int | 5 | Side length of square kernel |
| `iterations` | int | 1 | Number of dilation iterations |
| `shape` | str | `ellipse` | Kernel shape: `cross`, `ellipse`, or `rect` |

## CCL

Connected Component Labeling — finds connected blobs of white pixels and filters by minimum area.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `min_area` | int | 30 | Minimum blob area in pixels |
| `connectivity` | int | 8 | Pixel connectivity: 4 or 8 |
| `backend` | str | `opencv` | `opencv` or `scipy` |

OpenCV backend is ~15× faster than scipy on dense images.

## Contour Extract

Extract one line segment per blob by finding the farthest pair of contour extreme points.

No parameters. The algorithm finds the leftmost, rightmost, topmost, and bottommost contour points, then returns the pair with the greatest distance. Every blob produces exactly one line segment.

**Known limitation:** Crossing wires merge into one blob, producing one incorrect diagonal line. This accounts for ~14% of missed ground truth on the hand-drawn dataset.

## Dedup

Merge collinear and overlapping lines globally across all blobs.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `angle_thresh` | int | 10 | Angle threshold in degrees. Lines with angle difference below this are candidates for merging. Set to 0 to disable. |
| `dist_thresh` | int | 12 | Distance threshold in pixels. Both endpoints of the shorter line must be within this distance of the longer line. |

Two lines are duplicates if:
1. Their angle difference is below `angle_thresh`, AND
2. Both endpoints of the shorter line are within `dist_thresh` pixels of the longer line

When a duplicate pair is found, the longer line is kept and the shorter is removed.

## Length Filter

Remove lines shorter than a minimum length.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `min_length` | int | 0 | Minimum line length in pixels. 0 = no filtering. |
