from typing import Any
import numpy as np
import albumentations as A


def get_train_transforms(image_size: tuple[int, int] = (1024, 1024)) -> A.Compose:
    return A.Compose([
        A.Resize(image_size[0], image_size[1]),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.1),
        A.Rotate(limit=45, p=0.3),
        A.RandomBrightnessContrast(p=0.3),
        A.GaussNoise(p=0.2),
    ])


def get_eval_transforms(image_size: tuple[int, int] = (640, 640)) -> A.Compose:
    return A.Compose([
        A.Resize(image_size[0], image_size[1]),
    ])
