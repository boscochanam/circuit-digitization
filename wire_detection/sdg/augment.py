from typing import Any
import numpy as np
import albumentations as A


def get_sdg_augmentations(image_size: tuple[int, int] = (1024, 1024)) -> A.Compose:
    return A.Compose([
        A.GaussianBlur(blur_limit=(1, 3), p=0.3),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.3),
        A.GaussNoise(var_limit=(5, 20), p=0.2),
        A.Rotate(limit=10, p=0.2),
        A.Affine(scale=(0.9, 1.1), p=0.2),
    ])


def augment_image(image: np.ndarray, aug_pipeline: A.Compose) -> np.ndarray:
    augmented = aug_pipeline(image=image)
    return augmented["image"]
