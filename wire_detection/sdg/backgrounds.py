from pathlib import Path
import cv2
import numpy as np
import random

from wire_detection.sdg.textures import apply_unruled_background


class BackgroundLoader:
    def __init__(
        self,
        source_dir: Path | None = None,
        target_size: tuple[int, int] = (640, 640),
        crop_mode: str = "random",
        fallback_to_synthetic: bool = True,
        cache_size: int = 50,
    ):
        self.source_dir = Path(source_dir) if source_dir else None
        self.target_size = target_size
        self.crop_mode = crop_mode
        self.fallback_to_synthetic = fallback_to_synthetic
        self.cache_size = cache_size
        self._image_paths: list[Path] = []
        self._cache: dict[str, np.ndarray] = {}
        self._scan_images()

    def _scan_images(self):
        if self.source_dir is None or not self.source_dir.exists():
            self._image_paths = []
            return
        extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]
        self._image_paths = [
            p for p in self.source_dir.iterdir()
            if p.suffix.lower() in extensions
        ]

    @property
    def has_backgrounds(self) -> bool:
        return len(self._image_paths) > 0

    def get_background(self) -> np.ndarray:
        if not self.has_backgrounds:
            if self.fallback_to_synthetic:
                return self._generate_synthetic()
            raise RuntimeError("No background images found and fallback disabled")
        img_path = random.choice(self._image_paths)
        cache_key = str(img_path)
        if cache_key not in self._cache:
            img = cv2.imread(str(img_path))
            if img is None:
                return self._generate_synthetic()
            if len(self._cache) >= self.cache_size:
                del self._cache[random.choice(list(self._cache.keys()))]
            self._cache[cache_key] = img
        else:
            img = self._cache[cache_key]
        return self._crop(img)

    def _crop(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        target_w, target_h = self.target_size
        if w < target_w or h < target_h:
            scale = max(target_w / w, target_h / h) * 1.1
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            h, w = img.shape[:2]
        if self.crop_mode == "center":
            x = (w - target_w) // 2
            y = (h - target_h) // 2
        elif self.crop_mode == "random":
            x = random.randint(0, w - target_w)
            y = random.randint(0, h - target_h)
        else:
            x, y = 0, 0
        return img[y:y + target_h, x:x + target_w].copy()

    def _generate_synthetic(self) -> np.ndarray:
        target_w, target_h = self.target_size
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        return apply_unruled_background(canvas)


def generate_plain_background(size: tuple[int, int]) -> np.ndarray:
    return np.full((*size, 3), 255, dtype=np.uint8)


def generate_grid_background(size: tuple[int, int], grid_size: int = 50) -> np.ndarray:
    bg = np.full((*size, 3), 255, dtype=np.uint8)
    h, w = size
    color = 200
    for x in range(0, w, grid_size):
        cv2.line(bg, (x, 0), (x, h), (color, color, color), 1)
    for y in range(0, h, grid_size):
        cv2.line(bg, (0, y), (w, y), (color, color, color), 1)
    return bg


def generate_noise_background(size: tuple[int, int], noise_type: str = "gaussian") -> np.ndarray:
    h, w = size
    if noise_type == "gaussian":
        noise = np.random.normal(128, 30, (h, w)).astype(np.uint8)
    else:
        noise = np.random.randint(0, 255, (h, w), dtype=np.uint8)
    return np.dstack([noise] * 3)
