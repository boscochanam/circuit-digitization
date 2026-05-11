# API Endpoints

The FastAPI server runs on port 8000 and exposes the following endpoints:

## List Images

```
GET /api/list?ds=<dataset_key>
```

Returns a JSON array of image filenames for the specified dataset.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ds` | string | Yes | Dataset key (e.g., `hand_drawn`, `synthetic`, `hdc`) |

**Response:** `["image_001.jpg", "image_002.jpg", ...]`

## Get Thumbnail

```
GET /api/thumb?idx=<n>&ds=<dataset_key>
```

Returns a JPEG thumbnail of the specified image.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `idx` | int | Yes | Zero-based image index |
| `ds` | string | Yes | Dataset key |

**Response:** JPEG image (Content-Type: `image/jpeg`)

## List Datasets

```
GET /api/datasets
```

Returns information about all configured datasets.

**Response:**
```json
{
  "hand_drawn": {
    "path": "/data/hand_drawn",
    "image_count": 140,
    "description": "Hand-drawn circuit wires"
  },
  "synthetic": {
    "path": "/data/synthetic",
    "image_count": 2000,
    "description": "Synthetic bezier-curve wires"
  }
}
```

## Run Pipeline

```
POST /api/process
```

Runs the detection pipeline with configurable parameters.

**Request body (JSON):**
```json
{
  "idx": 0,
  "ds": "hand_drawn",
  "params": {
    "threshold_mode": "otsu",
    "dilate_kernel_size": 5,
    "dilate_iterations": 1,
    "ccl_min_area": 30,
    "dedup_angle": 10,
    "dedup_dist": 12,
    "min_line_length": 20
  }
}
```

**Response:**
```json
{
  "line_count": 42,
  "blob_count": 55,
  "elapsed_ms": 12.34,
  "overlay": "<base64 JPEG>",
  "threshold": "<base64 JPEG>",
  "dilated": "<base64 JPEG>",
  "masked": "<base64 JPEG>"
}
```

The `overlay`, `threshold`, `dilated`, and `masked` fields are base64-encoded JPEG images for the 4-panel display.

## List Stages

```
GET /api/stages
```

Returns available pipeline stages and their parameters.

**Response:**
```json
[
  {
    "name": "threshold",
    "params": {
      "mode": {"type": "select", "options": ["otsu", "manual", "adaptive"]},
      "value": {"type": "int", "min": 0, "max": 255, "default": 127}
    }
  }
]
```
