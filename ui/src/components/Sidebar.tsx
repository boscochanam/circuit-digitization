"use client";

import { useState } from "react";
import type { PresetMap } from "@/lib/types";
import type { ComponentEntry } from "@/lib/types";
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
  R: "#0000FF", C: "#FF0000", L: "#008000", J: "#000000",
  T: "#666666", D: "#8B00FF", Q: "#FF6600", V: "#0066CC",
};

// Only R, C, L, V have SPICE models → only these carry an editable value.
// (Editability is derived from the SPICE name prefix everywhere — same rule the
// in-place popover and the backend's index→SPICE mapping use.)
const VALUE_PLACEHOLDER: Record<string, string> = { R: "10k", C: "100n", L: "10m", V: "5V" };
const isEditable = (name: string) => /^[RCLV]/.test(name);

type SidebarTab = "params" | "components";

export default function Sidebar({
  presetParams,
  onPresetParamChange,
  isLegacy,
  legacyParams,
  onLegacyParamChange,
  preset,
  presets,
  components,
  selectedComponent,
  onComponentSelect,
  onComponentValueChange,
}: SidebarProps) {
  const [tab, setTab] = useState<SidebarTab>("params");

  const editable = components.filter((c) => isEditable(c.name));
  const others = components.filter((c) => !isEditable(c.name));

  return (
    <aside className="sidebar-layout">
      {/* Two concerns, each gets the full sidebar height. Join inspection lives in
          its own view (View bar → Join check), not crammed in here. */}
      <div className="sidebar-tabs">
        <button className={`sidebar-tab ${tab === "params" ? "sidebar-tab-active" : ""}`} onClick={() => setTab("params")}>Params</button>
        <button className={`sidebar-tab ${tab === "components" ? "sidebar-tab-active" : ""}`} onClick={() => setTab("components")}>
          Values{editable.length ? ` ${editable.length}` : ""}
        </button>
      </div>

      <div className="sidebar-tab-body">
        {/* ── PARAMETERS ── */}
        {tab === "params" && (
          <div className="sidebar-section">
            {!isLegacy ? (
              <>
                <ParamGroup title="Thresholding">
                  <ParamSlider label="Sauvola k" value={presetParams.sauvola_k ?? 0.285} min={0.05} max={0.6} step={0.005} onChange={(v) => onPresetParamChange("sauvola_k", v)} />
                  <ParamSlider label="Window" value={presetParams.sauvola_window ?? 67} min={3} max={151} step={2} onChange={(v) => onPresetParamChange("sauvola_window", v)} />
                  <ParamSlider label="Close Kernel" value={presetParams.close_kernel ?? 3} min={1} max={15} step={2} onChange={(v) => onPresetParamChange("close_kernel", v)} />
                </ParamGroup>
                <ParamGroup title="Component Filtering">
                  <ParamSlider label="CCL Min Area" value={presetParams.ccl_min_area ?? 28} min={0} max={100} step={1} onChange={(v) => onPresetParamChange("ccl_min_area", v)} />
                </ParamGroup>
                <ParamGroup title="Deduplication">
                  <ParamSlider label="Angle" value={presetParams.dedup_angle ?? 10} min={0} max={45} step={1} unit="°" onChange={(v) => onPresetParamChange("dedup_angle", v)} />
                  <ParamSlider label="Distance" value={presetParams.dedup_dist ?? 18} min={0} max={50} step={1} unit="px" onChange={(v) => onPresetParamChange("dedup_dist", v)} />
                </ParamGroup>
                <ParamGroup title="Anchor Filter">
                  <ParamSlider label="Endpoint Dist" value={presetParams.anchor_endpoint_dist ?? 12} min={0} max={30} step={0.5} onChange={(v) => onPresetParamChange("anchor_endpoint_dist", v)} />
                  <ParamSlider label="Link Dist" value={presetParams.anchor_link_dist ?? 8} min={0} max={20} step={0.5} onChange={(v) => onPresetParamChange("anchor_link_dist", v)} />
                </ParamGroup>
                <button className="reset-btn" onClick={() => {
                  const p = presets[preset];
                  if (p?.params) for (const [k, v] of Object.entries(p.params)) onPresetParamChange(k, v);
                }}>Reset to Defaults</button>
              </>
            ) : (
              <>
                <ParamGroup title="Thresholding">
                  <ParamSlider label="Dilate Kernel" value={legacyParams.dil_ksize as number} min={1} max={15} step={2} onChange={(v) => onLegacyParamChange("dil_ksize", v)} />
                  <ParamSlider label="Dilate Iters" value={legacyParams.dil_iters as number} min={0} max={5} step={1} onChange={(v) => onLegacyParamChange("dil_iters", v)} />
                </ParamGroup>
                <ParamGroup title="Filtering">
                  <ParamSlider label="Min Area" value={legacyParams.min_area as number} min={0} max={200} step={5} onChange={(v) => onLegacyParamChange("min_area", v)} />
                  <ParamSlider label="Dedup Angle" value={legacyParams.dedup_angle as number} min={0} max={45} step={1} unit="°" onChange={(v) => onLegacyParamChange("dedup_angle", v)} />
                  <ParamSlider label="Dedup Dist" value={legacyParams.dedup_dist as number} min={0} max={50} step={1} unit="px" onChange={(v) => onLegacyParamChange("dedup_dist", v)} />
                  <ParamSlider label="Min Length" value={legacyParams.min_line_length as number} min={0} max={500} step={5} onChange={(v) => onLegacyParamChange("min_line_length", v)} />
                </ParamGroup>
              </>
            )}
          </div>
        )}

        {/* ── VALUES (the interactive value editor) ── */}
        {tab === "components" && (
          <div className="sidebar-section">
            {components.length === 0 ? (
              <div className="sidebar-empty">No components for this image.</div>
            ) : (
              <>
                <p className="sidebar-help" style={{ marginTop: 0 }}>
                  Set values for R / C / L / V, then open the <strong>Voltage</strong> view
                  to simulate. At the DC operating point only <strong>R</strong> and{" "}
                  <strong>V</strong> change the map (C / L are tagged <em>no DC</em>). You can
                  also click a component on the image to edit it in place.
                </p>

                {editable.length === 0 ? (
                  <div className="sidebar-empty">No R/C/L/V components on this image.</div>
                ) : (
                  <div className="value-editor">
                    {editable.map((comp) => {
                      const t = comp.name.charAt(0);
                      const color = COMPONENT_TYPE_COLORS[t] ?? "#666666";
                      // The voltage map is a DC operating point: caps are open and
                      // inductors short, so only R and V change it. Flag C/L so a
                      // no-op edit isn't mistaken for a broken feature.
                      const affectsDC = t === "R" || t === "V";
                      return (
                        <label
                          key={comp.name}
                          className={`value-row ${selectedComponent === comp.name ? "value-row-active" : ""}`}
                          onClick={() => onComponentSelect(comp.name)}
                          title={affectsDC ? undefined : `${comp.name} is open at DC — its value does not change the voltage map (matters for AC/transient analysis)`}
                        >
                          <span className="value-row-dot" style={{ background: color }} />
                          <span className="value-row-name">{comp.name}</span>
                          {!affectsDC && <span className="value-row-tag" title="No effect on the DC voltage map">no DC</span>}
                          <input
                            className="value-row-input"
                            value={comp.value}
                            onChange={(e) => onComponentValueChange(comp.name, e.target.value)}
                            placeholder={VALUE_PLACEHOLDER[t] ?? "--"}
                          />
                        </label>
                      );
                    })}
                  </div>
                )}

                {others.length > 0 && (
                  <details className="value-others">
                    <summary>{others.length} non-editable (junctions, text, diodes…)</summary>
                    <div className="value-others-list">
                      {others.map((c) => {
                        const color = COMPONENT_TYPE_COLORS[c.name.charAt(0)] ?? "#666666";
                        return (
                          <span key={c.name} className="value-others-chip">
                            <span className="value-row-dot" style={{ background: color }} />
                            {c.name}
                          </span>
                        );
                      })}
                    </div>
                  </details>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
