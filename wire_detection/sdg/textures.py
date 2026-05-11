import cv2
import numpy as np
import random
import math


def apply_unruled_background(canvas: np.ndarray) -> np.ndarray:
    h, w = canvas.shape[:2]
    base_tone = random.randint(200, 230)
    tint = np.random.randint(-5, 5, 3)
    paper_color = np.clip(
        [base_tone + tint[0], base_tone + tint[1], base_tone + tint[2]],
        180, 240
    )
    canvas[:] = paper_color
    noise = np.random.normal(0, 3, (h, w, 3)).astype(np.int16)
    canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    X, Y = np.meshgrid(np.arange(w), np.arange(h))
    a, b = random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)
    gradient = a * X + b * Y
    if gradient.max() != gradient.min():
        gradient = (gradient - gradient.min()) / (gradient.max() - gradient.min())
    else:
        gradient = np.ones_like(gradient) * 0.5
    gradient = 0.85 + (0.15 * gradient)
    gradient = np.dstack([gradient] * 3)
    return (canvas.astype(float) * gradient).astype(np.uint8)


def add_paper_imperfections(canvas: np.ndarray) -> np.ndarray:
    h, w = canvas.shape[:2]
    for _ in range(random.randint(0, 2)):
        radius = random.randint(2, 8)
        cx, cy = random.randint(0, w), random.randint(0, h)
        tone = random.randint(100, 180)
        overlay = canvas.copy()
        cv2.circle(overlay, (cx, cy), radius, (tone, tone, tone), -1)
        overlay = cv2.GaussianBlur(overlay, (15, 15), 0)
        cv2.addWeighted(overlay, 0.3, canvas, 0.7, 0, canvas)
    for _ in range(random.randint(30, 80)):
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        color = random.randint(80, 150)
        canvas[y, x] = (color, color, color)
    num_marks = random.randint(5, 15)
    for _ in range(num_marks):
        mark_type = random.choice(["hair", "slip", "ghost"])
        sx, sy = random.randint(0, w), random.randint(0, h)
        if mark_type == "hair":
            ex = sx + random.randint(-20, 20)
            ey = sy + random.randint(-20, 20)
            cx = (sx + ex) // 2 + random.randint(-5, 5)
            cy = (sy + ey) // 2 + random.randint(-5, 5)
            pts = np.array([[sx, sy], [cx, cy], [ex, ey]], np.int32)
            pts = pts.reshape((-1, 1, 2))
            color = (random.randint(100, 160),) * 3
            cv2.polylines(canvas, [pts], False, color, 1, cv2.LINE_AA)
        elif mark_type == "slip":
            length = random.randint(5, 15)
            angle = random.uniform(0, 2 * math.pi)
            ex = int(sx + length * math.cos(angle))
            ey = int(sy + length * math.sin(angle))
            color = (random.randint(80, 140),) * 3
            cv2.line(canvas, (sx, sy), (ex, ey), color, 1, cv2.LINE_AA)
        elif mark_type == "ghost":
            ex = sx + random.randint(-100, 100)
            ey = sy + random.randint(-100, 100)
            overlay = canvas.copy()
            cv2.line(overlay, (sx, sy), (ex, ey), (150, 150, 150), 1, cv2.LINE_AA)
            cv2.addWeighted(overlay, 0.15, canvas, 0.85, 0, canvas)
    return canvas


def apply_texture_mask(stroke_layer: np.ndarray, intensity: float = 0.5) -> np.ndarray:
    if intensity <= 0.05:
        return stroke_layer
    h, w = stroke_layer.shape[:2]
    noise = np.random.randint(0, 255, (h, w), dtype=np.uint8)
    mask = (noise > (255 * intensity)).astype(np.uint8)
    mask_3c = np.dstack([mask] * 3)
    return cv2.multiply(stroke_layer, mask_3c)


def draw_tool_stroke(canvas: np.ndarray, points: np.ndarray, tool_type: str):
    stroke_layer = np.zeros_like(canvas)
    if tool_type == "pencil":
        c = random.randint(80, 140)
        color = (c, c, c)
        thickness = random.randint(1, 2)
        cv2.polylines(stroke_layer, [points], False, color, thickness, cv2.LINE_8)
        textured = apply_texture_mask(stroke_layer, intensity=0.1)
        mask = np.any(textured > 0, axis=-1)
        canvas[mask] = cv2.addWeighted(canvas[mask], 0.3, textured[mask], 0.7, 0)
    elif tool_type == "ballpoint":
        if random.random() > 0.5:
            base_color = (
                random.randint(60, 100),
                random.randint(20, 50),
                random.randint(20, 50),
            )
        else:
            c = random.randint(40, 80)
            base_color = (c, c, c)
        thickness = random.randint(1, 2)
        for i in range(len(points) - 1):
            if random.random() < 0.02:
                continue
            p1, p2 = tuple(points[i]), tuple(points[i + 1])
            cv2.line(stroke_layer, p1, p2, base_color, thickness, cv2.LINE_8)
        textured = apply_texture_mask(stroke_layer, intensity=0.05)
        mask = np.any(textured > 0, axis=-1)
        canvas[mask] = textured[mask]
    elif tool_type == "gel":
        c = random.randint(20, 60)
        color = (c, c, c)
        thickness = random.randint(1, 2)
        cv2.polylines(stroke_layer, [points], False, color, thickness, cv2.LINE_8)
        mask = np.any(stroke_layer > 0, axis=-1)
        canvas[mask] = stroke_layer[mask]
