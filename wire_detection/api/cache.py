from collections import OrderedDict
from typing import Any
import threading
import cv2
import numpy as np


class ImageCache:
    def __init__(self, maxsize: int = 200):
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str) -> np.ndarray | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: str, image: np.ndarray) -> None:
        with self._lock:
            self._cache[key] = image
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def load_image(self, path: str, resize: int | None = None) -> np.ndarray:
        key = f"{path}:{resize}"
        cached = self.get(key)
        if cached is not None:
            return cached

        image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"Cannot read image: {path}")

        if resize:
            h, w = image.shape
            scale = resize / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        self.put(key, image)
        return image
