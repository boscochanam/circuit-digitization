/**
 * Panel constants — named indices instead of magic numbers.
 *
 * The UI has two layers of navigation:
 *   1. **Stage tabs** (Detect / Netlist / Simulate) — primary workflow progression
 *   2. **Sub-tabs** within each stage — specific views
 *
 * Legacy flat-panel indices are preserved for backward compatibility during migration.
 */

// ── Stage definitions ──
export const STAGES = ["Detect", "Netlist", "Simulate"] as const;
export type Stage = (typeof STAGES)[number];

// ── Panel indices (legacy flat mapping) ──
export const PANEL = {
  // Stage: Detect
  DETECTED_LINES: 0,
  THRESHOLD: 1,
  DILATED_CLOSED: 2,
  SOURCE: 3,

  // Stage: Netlist
  NETLIST: 4,
  JOIN_CHECK: 7,

  // Stage: Simulate
  SIMULATION: 5,
  TOPOLOGY: 6,
  VOLTAGE_MAP: 8,
} as const;

export type PanelIndex = (typeof PANEL)[keyof typeof PANEL];

// ── Human-readable panel names (full, no truncation) ──
export const PANEL_NAMES: Record<PanelIndex, string> = {
  [PANEL.DETECTED_LINES]: "Detected Lines",
  [PANEL.THRESHOLD]: "Threshold",
  [PANEL.DILATED_CLOSED]: "Dilated / Closed",
  [PANEL.SOURCE]: "Source",
  [PANEL.NETLIST]: "Netlist",
  [PANEL.SIMULATION]: "Simulation",
  [PANEL.TOPOLOGY]: "Topology",
  [PANEL.JOIN_CHECK]: "Join Check",
  [PANEL.VOLTAGE_MAP]: "Voltage Map",
};

// ── Stage → panel mapping ──
export const STAGE_PANELS: Record<Stage, readonly PanelIndex[]> = {
  Detect: [PANEL.DETECTED_LINES, PANEL.THRESHOLD, PANEL.DILATED_CLOSED, PANEL.SOURCE],
  Netlist: [PANEL.NETLIST, PANEL.JOIN_CHECK],
  Simulate: [PANEL.SIMULATION, PANEL.TOPOLOGY, PANEL.VOLTAGE_MAP],
} as const;

// ── Panel → stage reverse lookup ──
export function panelToStage(panel: number): Stage {
  if (panel <= 3) return "Detect";
  if (panel === 4 || panel === 7) return "Netlist";
  return "Simulate";
}

// ── Legacy array (deprecated — use STAGE_PANELS instead) ──
export const IMAGE_PANELS = [
  "Detected Lines", "Threshold", "Dilated / Closed", "Source",
  "Netlist", "Simulation", "Topology", "Join Check", "Voltage Map",
] as const;
