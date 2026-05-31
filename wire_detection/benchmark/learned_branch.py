from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import albumentations as A
import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from wire_detection.benchmark import experiment_harness as eh
from wire_detection.benchmark import reference_pipeline as ref
from wire_detection.sdg.generator import SDG, SDGConfig


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


@dataclass(slots=True)
class LearnedConfig:
    image_size: int = 256
    synthetic_count: int = 400
    synthetic_epochs: int = 4
    finetune_epochs: int = 12
    batch_size: int = 8
    lr: float = 1e-3
    seed: int = 7
    line_thickness: int = 5
    threshold: float = 0.5
    post_cfg_name: str = "best_candidate_v7"


class DoubleConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TinyUNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.d1 = DoubleConv(1, 32)
        self.d2 = DoubleConv(32, 64)
        self.d3 = DoubleConv(64, 128)
        self.u2 = DoubleConv(128 + 64, 64)
        self.u1 = DoubleConv(64 + 32, 32)
        self.out = nn.Conv2d(32, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.d1(x)
        x2 = self.d2(F.max_pool2d(x1, 2))
        x3 = self.d3(F.max_pool2d(x2, 2))
        y = F.interpolate(x3, scale_factor=2, mode="bilinear", align_corners=False)
        y = self.u2(torch.cat([y, x2], dim=1))
        y = F.interpolate(y, scale_factor=2, mode="bilinear", align_corners=False)
        y = self.u1(torch.cat([y, x1], dim=1))
        return self.out(y)


def dice_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    num = 2 * (probs * targets).sum(dim=(1, 2, 3)) + 1e-6
    den = probs.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3)) + 1e-6
    return 1 - (num / den).mean()


def build_post_cfg(name: str) -> eh.ExperimentConfig:
    for cfg in eh.wave3_configs() + eh.wave2_configs() + eh.wave1_configs():
        if cfg.name == name:
            return cfg
    raise KeyError(f"Unknown post-processing config: {name}")


def make_target_mask(
    lines: list[tuple[tuple[int, int], tuple[int, int]]],
    shape: tuple[int, int],
    thickness: int,
) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    for (x1, y1), (x2, y2) in lines:
        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness)
    return mask


class GroundTruthWireDataset(Dataset):
    def __init__(self, cfg: LearnedConfig, augment: bool):
        self.cfg = cfg
        self.items: list[dict[str, object]] = []
        self.aug = None
        if augment:
            self.aug = A.Compose(
                [
                    A.Affine(scale=(0.9, 1.05), translate_percent=(-0.04, 0.04), rotate=(-4, 4), p=0.8),
                    A.RandomBrightnessContrast(0.15, 0.15, p=0.7),
                    A.GaussNoise(std_range=(0.01, 0.04), p=0.4),
                    A.GaussianBlur(blur_limit=(3, 5), p=0.2),
                ]
            )
        post_cfg = build_post_cfg(cfg.post_cfg_name)
        for gt_file in sorted(ref.GT_LABELS.glob("*_jpg.txt")):
            image_name = gt_file.stem.replace("_jpg", "")
            image_path = ref.GT_IMAGES / f"{image_name}_jpg.jpg"
            gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                continue
            h, w = gray.shape
            gt_lines = ref.load_ground_truth(gt_file, w, h)
            hdc_label = ref.find_hdc_label(image_name, gray)
            components = ref.parse_components(hdc_label, w, h)
            occluded = eh.build_component_mask(gray, components, post_cfg.occlusion_margin)
            if components:
                cropped, ox, oy = eh.crop_to_roi(occluded, components, post_cfg.crop_padding)
                cropped_lines = [((x1 - ox, y1 - oy), (x2 - ox, y2 - oy)) for (x1, y1), (x2, y2) in gt_lines]
            else:
                cropped = occluded
                cropped_lines = gt_lines
            mask = make_target_mask(cropped_lines, cropped.shape, cfg.line_thickness)
            self.items.append({"image": cropped, "mask": mask, "name": image_name})

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        item = self.items[idx]
        image = item["image"].copy()
        mask = item["mask"].copy()
        resized_image = cv2.resize(image, (self.cfg.image_size, self.cfg.image_size), interpolation=cv2.INTER_AREA)
        resized_mask = cv2.resize(mask, (self.cfg.image_size, self.cfg.image_size), interpolation=cv2.INTER_NEAREST)
        if self.aug is not None:
            transformed = self.aug(image=resized_image, mask=resized_mask)
            resized_image = transformed["image"]
            resized_mask = transformed["mask"]
        x = torch.from_numpy(resized_image.astype(np.float32) / 255.0).unsqueeze(0)
        y = torch.from_numpy((resized_mask > 0).astype(np.float32)).unsqueeze(0)
        return x, y


class SyntheticWireDataset(Dataset):
    def __init__(self, cfg: LearnedConfig):
        self.cfg = cfg
        self.sdg = SDG(
            SDGConfig(
                num_images=cfg.synthetic_count,
                image_size=(cfg.image_size, cfg.image_size),
                label_format="lines",
                seed=cfg.seed,
                components_count=(4, 8),
                components_size=(40, 120),
                safe_buffer=12,
            )
        )

    def __len__(self) -> int:
        return self.cfg.synthetic_count

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        rng = np.random.default_rng(self.cfg.seed + idx)
        image, lines = self.sdg.generate_one(rng)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = make_target_mask(lines, gray.shape, self.cfg.line_thickness)
        x = torch.from_numpy(gray.astype(np.float32) / 255.0).unsqueeze(0)
        y = torch.from_numpy((mask > 0).astype(np.float32)).unsqueeze(0)
        return x, y


def train_epoch(model: nn.Module, loader: DataLoader, opt: torch.optim.Optimizer, device: torch.device) -> float:
    model.train()
    total = 0.0
    for x, y in loader:
        x = x.to(device)
        y = y.to(device)
        opt.zero_grad(set_to_none=True)
        logits = model(x)
        loss = F.binary_cross_entropy_with_logits(logits, y) + dice_loss(logits, y)
        loss.backward()
        opt.step()
        total += float(loss.item()) * x.size(0)
    return total / max(len(loader.dataset), 1)


def predict_mask(model: nn.Module, gray: np.ndarray, cfg: LearnedConfig, device: torch.device) -> np.ndarray:
    resized = cv2.resize(gray, (cfg.image_size, cfg.image_size), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(x)
        probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
    pred = (probs >= cfg.threshold).astype(np.uint8) * 255
    return cv2.resize(pred, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST)


def evaluate_model(model: nn.Module, cfg: LearnedConfig, device: torch.device, output_dir: Path | None = None) -> dict[str, object]:
    post_cfg = build_post_cfg(cfg.post_cfg_name)
    rows = []
    tp_t = fp_t = fn_t = red_t = 0
    for gt_file in sorted(ref.GT_LABELS.glob("*_jpg.txt")):
        image_name = gt_file.stem.replace("_jpg", "")
        image_path = ref.GT_IMAGES / f"{image_name}_jpg.jpg"
        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        h, w = gray.shape
        gt_lines = ref.load_ground_truth(gt_file, w, h)
        hdc_label = ref.find_hdc_label(image_name, gray)
        components = ref.parse_components(hdc_label, w, h)
        occluded = eh.build_component_mask(gray, components, post_cfg.occlusion_margin)
        if components:
            cropped, ox, oy = eh.crop_to_roi(occluded, components, post_cfg.crop_padding)
            local_components = eh.shift_components(components, ox, oy)
        else:
            cropped, ox, oy = occluded, 0, 0
            local_components = []
        pred_mask = predict_mask(model, cropped, cfg, device)
        masks = [pred_mask]
        fused_mask, support_map = eh.fuse_masks(masks, 1)
        candidates = eh.extract_lines_from_skeleton(fused_mask, support_map, local_components, post_cfg)
        lines_local = eh.reconnect_lines(candidates, local_components, post_cfg)
        lines_local = eh.filter_component_connected_lines(lines_local, local_components, post_cfg)
        lines_local = eh.snap_line_endpoints(lines_local, local_components, post_cfg)
        lines_global = [((x1 + ox, y1 + oy), (x2 + ox, y2 + oy)) for (x1, y1), (x2, y2) in lines_local]
        tp, fp, fn, red = ref.evaluate(lines_global, gt_lines)
        tp_t += tp
        fp_t += fp
        fn_t += fn
        red_t += red
        p = tp / max(tp + fp + red, 1)
        r = tp / max(tp + fn, 1)
        f1 = 2 * p * r / max(p + r, 1e-8)
        rows.append({"image": image_name, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "red": red})
        if output_dir is not None:
            overlay_dir = output_dir / "overlays"
            overlay_dir.mkdir(parents=True, exist_ok=True)
            eh.draw_overlay(gray, lines_global, gt_lines, overlay_dir / f"{image_name}.png")
    precision = tp_t / max(tp_t + fp_t + red_t, 1)
    recall = tp_t / max(tp_t + fn_t, 1)
    global_f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    return {
        "config": asdict(cfg),
        "global_f1": global_f1,
        "precision": precision,
        "recall": recall,
        "tp": tp_t,
        "fp": fp_t,
        "fn": fn_t,
        "red": red_t,
        "images": rows,
    }


def run_learned_branch(cfg: LearnedConfig, output_dir: Path) -> dict[str, object]:
    set_seed(cfg.seed)
    device = torch.device("cpu")
    model = TinyUNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    syn_loader = DataLoader(SyntheticWireDataset(cfg), batch_size=cfg.batch_size, shuffle=True)
    gt_loader = DataLoader(GroundTruthWireDataset(cfg, augment=True), batch_size=min(cfg.batch_size, 4), shuffle=True)

    train_log: list[dict[str, float]] = []
    for epoch in range(cfg.synthetic_epochs):
        loss = train_epoch(model, syn_loader, opt, device)
        train_log.append({"phase": "synthetic", "epoch": epoch + 1, "loss": loss})
    for epoch in range(cfg.finetune_epochs):
        loss = train_epoch(model, gt_loader, opt, device)
        train_log.append({"phase": "finetune", "epoch": epoch + 1, "loss": loss})

    summary = evaluate_model(model, cfg, device, output_dir)
    summary["train_log"] = train_log
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "model.pt")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a lightweight learned wire-mask branch")
    parser.add_argument("--output-dir", type=Path, default=Path("output/learned_wire_branch"))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--synthetic-count", type=int, default=400)
    parser.add_argument("--synthetic-epochs", type=int, default=4)
    parser.add_argument("--finetune-epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--line-thickness", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--post-cfg-name", type=str, default="best_candidate_v7")
    args = parser.parse_args()

    cfg = LearnedConfig(
        image_size=args.image_size,
        synthetic_count=args.synthetic_count,
        synthetic_epochs=args.synthetic_epochs,
        finetune_epochs=args.finetune_epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        line_thickness=args.line_thickness,
        threshold=args.threshold,
        post_cfg_name=args.post_cfg_name,
    )
    summary = run_learned_branch(cfg, args.output_dir)
    print(
        f"learned_branch\t{summary['global_f1']:.4f}\t{summary['precision']:.4f}\t"
        f"{summary['recall']:.4f}\t{summary['tp']}\t{summary['fp']}\t{summary['fn']}\t{summary['red']}"
    )


if __name__ == "__main__":
    main()
