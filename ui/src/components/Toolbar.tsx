"use client";

import type { PresetMap } from "@/lib/types";

interface ToolbarProps {
  imageIdx: number;
  imageCount: number;
  dataset: string;
  preset: string;
  onPrev: () => void;
  onNext: () => void;
  onDatasetChange: (ds: string) => void;
  onPresetChange: (preset: string) => void;
  presets: PresetMap;
}

const DATASETS = ["gt_labels", "hdc", "synthetic"] as const;
const DATASET_LABELS: Record<string, string> = {
  gt_labels: "GT Labels",
  hdc: "HDC (1680)",
  synthetic: "Synthetic",
};

export default function Toolbar({
  imageIdx,
  imageCount,
  dataset,
  preset,
  onPrev,
  onNext,
  onDatasetChange,
  onPresetChange,
  presets,
}: ToolbarProps) {
  return (
    <header className="toolbar-root">
      <div className="toolbar-section">
        <button
          className="toolbar-nav-btn"
          onClick={onPrev}
          disabled={imageIdx === 0}
          aria-label="Previous image"
        >
          &#9664;
        </button>
        <span className="toolbar-counter">
          {imageIdx + 1}/{imageCount}
        </span>
        <button
          className="toolbar-nav-btn"
          onClick={onNext}
          disabled={imageIdx >= imageCount - 1}
          aria-label="Next image"
        >
          &#9654;
        </button>
      </div>

      <div className="toolbar-section">
        <label className="toolbar-label">DS</label>
        <select
          value={dataset}
          onChange={(e) => onDatasetChange(e.target.value)}
          className="toolbar-select"
        >
          {DATASETS.map((d) => (
            <option key={d} value={d}>
              {DATASET_LABELS[d] ?? d}
            </option>
          ))}
        </select>
      </div>

      <div className="toolbar-section">
        <label className="toolbar-label">Preset</label>
        <select
          value={preset}
          onChange={(e) => onPresetChange(e.target.value)}
          className="toolbar-select"
        >
          {Object.entries(presets).map(([key, p]) => (
            <option key={key} value={key}>
              {p.label}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
