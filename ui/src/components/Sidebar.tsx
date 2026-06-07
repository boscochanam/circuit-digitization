"use client";

import type { PresetMap } from "@/lib/types";
import type { ComponentEntry } from "@/stores/appStore";
import { ParamGroup, ParamSlider } from "@/components/ui-widgets";

interface SidebarProps {
  // Pipeline params
  presetParams: Record<string, number>;
  onPresetParamChange: (key: string, value: number) => void;
  isLegacy: boolean;
  legacyParams: Record<string, number | string>;
  onLegacyParamChange: (key: string, value: number | string) => void;

  // Preset
  preset: string;
  presets: PresetMap;
  onPresetChange: (preset: string) => void;

  // Components
  components: ComponentEntry[];
  selectedComponent: string | null;
  onComponentSelect: (name: string) => void;
  onComponentValueChange: (name: string, value: string) => void;
}

const COMPONENT_TYPE_COLORS: Record<string, string> = {
  R: "#0000FF",
  C: "#FF0000",
  L: "#008000",
  J: "#000000",
  T: "#666666",
  D: "#8B00FF",
  Q: "#FF6600",
  V: "#0066CC",
};

export default function Sidebar({
  presetParams,
  onPresetParamChange,
  isLegacy,
  legacyParams,
  onLegacyParamChange,
  preset,
  presets,
  onPresetChange,
  components,
  selectedComponent,
  onComponentSelect,
  onComponentValueChange,
}: SidebarProps) {
  return (
    <aside className="sidebar-layout">
      {/* ── Pipeline Preset ── */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">Pipeline Preset</div>
        <select
          value={preset}
          onChange={(e) => onPresetChange(e.target.value)}
          className="preset-select"
        >
          {Object.entries(presets).map(([key, p]) => (
            <option key={key} value={key}>
              {p.label}
            </option>
          ))}
        </select>
        {presets[preset]?.description && (
          <div className="preset-desc">{presets[preset].description}</div>
        )}
      </div>

      {/* ── Parameters ── */}
      <div className="sidebar-section sidebar-scroll">
        <div className="sidebar-section-label">Parameters</div>
        {!isLegacy ? (
          <>
            <ParamGroup title="Thresholding">
              <ParamSlider
                label="Sauvola k"
                value={presetParams.sauvola_k ?? 0.285}
                min={0.05}
                max={0.6}
                step={0.005}
                onChange={(v) => onPresetParamChange("sauvola_k", v)}
              />
              <ParamSlider
                label="Window"
                value={presetParams.sauvola_window ?? 67}
                min={3}
                max={151}
                step={2}
                onChange={(v) => onPresetParamChange("sauvola_window", v)}
              />
              <ParamSlider
                label="Close Kernel"
                value={presetParams.close_kernel ?? 3}
                min={1}
                max={15}
                step={2}
                onChange={(v) => onPresetParamChange("close_kernel", v)}
              />
            </ParamGroup>
            <ParamGroup title="Component Filtering">
              <ParamSlider
                label="CCL Min Area"
                value={presetParams.ccl_min_area ?? 28}
                min={0}
                max={100}
                step={1}
                onChange={(v) => onPresetParamChange("ccl_min_area", v)}
              />
            </ParamGroup>
            <ParamGroup title="Deduplication">
              <ParamSlider
                label="Angle"
                value={presetParams.dedup_angle ?? 10}
                min={0}
                max={45}
                step={1}
                unit="°"
                onChange={(v) => onPresetParamChange("dedup_angle", v)}
              />
              <ParamSlider
                label="Distance"
                value={presetParams.dedup_dist ?? 18}
                min={0}
                max={50}
                step={1}
                unit="px"
                onChange={(v) => onPresetParamChange("dedup_dist", v)}
              />
            </ParamGroup>
            <ParamGroup title="Anchor Filter">
              <ParamSlider
                label="Endpoint Dist"
                value={presetParams.anchor_endpoint_dist ?? 12}
                min={0}
                max={30}
                step={0.5}
                onChange={(v) => onPresetParamChange("anchor_endpoint_dist", v)}
              />
              <ParamSlider
                label="Link Dist"
                value={presetParams.anchor_link_dist ?? 8}
                min={0}
                max={20}
                step={0.5}
                onChange={(v) => onPresetParamChange("anchor_link_dist", v)}
              />
            </ParamGroup>
            <button
              className="reset-btn"
              onClick={() => {
                const p = presets[preset];
                if (p?.params) {
                  for (const [k, v] of Object.entries(p.params)) {
                    onPresetParamChange(k, v);
                  }
                }
              }}
            >
              Reset to Defaults
            </button>
          </>
        ) : (
          <>
            <ParamGroup title="Thresholding">
              <ParamSlider
                label="Dilate Kernel"
                value={legacyParams.dil_ksize as number}
                min={1}
                max={15}
                step={2}
                onChange={(v) => onLegacyParamChange("dil_ksize", v)}
              />
              <ParamSlider
                label="Dilate Iters"
                value={legacyParams.dil_iters as number}
                min={0}
                max={5}
                step={1}
                onChange={(v) => onLegacyParamChange("dil_iters", v)}
              />
            </ParamGroup>
            <ParamGroup title="Filtering">
              <ParamSlider
                label="Min Area"
                value={legacyParams.min_area as number}
                min={0}
                max={200}
                step={5}
                onChange={(v) => onLegacyParamChange("min_area", v)}
              />
              <ParamSlider
                label="Dedup Angle"
                value={legacyParams.dedup_angle as number}
                min={0}
                max={45}
                step={1}
                unit="°"
                onChange={(v) => onLegacyParamChange("dedup_angle", v)}
              />
              <ParamSlider
                label="Dedup Dist"
                value={legacyParams.dedup_dist as number}
                min={0}
                max={50}
                step={1}
                unit="px"
                onChange={(v) => onLegacyParamChange("dedup_dist", v)}
              />
              <ParamSlider
                label="Min Length"
                value={legacyParams.min_line_length as number}
                min={0}
                max={500}
                step={5}
                onChange={(v) => onLegacyParamChange("min_line_length", v)}
              />
            </ParamGroup>
          </>
        )}
      </div>

      {/* ── Component List ── */}
      {components.length > 0 && (
        <div className="sidebar-section sidebar-scroll">
          <div className="sidebar-section-label">
            Components ({components.length})
          </div>
          <div className="sidebar-component-list">
            {components.map((comp) => {
              const color = COMPONENT_TYPE_COLORS[comp.type] ?? "#666666";
              return (
                <button
                  key={comp.name}
                  className={`sidebar-component-item ${selectedComponent === comp.name ? "sidebar-component-active" : ""}`}
                  onClick={() => onComponentSelect(comp.name)}
                >
                  <span
                    className="sidebar-component-dot"
                    style={{ background: color }}
                  />
                  <span className="sidebar-component-name">{comp.name}</span>
                  <input
                    className="sidebar-component-value"
                    value={comp.value}
                    onChange={(e) =>
                      onComponentValueChange(comp.name, e.target.value)
                    }
                    onClick={(e) => e.stopPropagation()}
                    placeholder="--"
                  />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}
