export interface PipelineResult {
  line_count: number;
  blob_count: number;
  elapsed_ms: number;
  overlay: string;
  threshold: string;
  dilated: string;
  close?: string;
  preset?: string;
  params?: Record<string, unknown>;
  lines?: Array<{ ep1: [number, number]; ep2: [number, number] }>;
  components?: Array<{
    class_id: number;
    name: string;
    bbox: [number, number, number, number];
    vertices: Array<[number, number]>;
  }>;
}

export type PresetMap = Record<
  string,
  { label: string; description: string; params?: Record<string, number> }
>;

export type DatasetMap = Record<
  string,
  { path: string; images: number; sample: string | null }
>;

export interface NetlistResult {
  spice_netlist: string;
  nodes: Array<{
    id: number;
    pins: Array<{ component: string; pin: string }>;
  }>;
  components: Array<{
    name: string;
    type: string;
    pins: string[];
    position?: { x: number; y: number };
  }>;
  connections: Array<{
    from: { component: string; pin: string };
    to: { component: string; pin: string };
    wire_idx: number;
  }>;
  simulation?: SimulationResult;
  warnings: string[];
}

export interface SimulationResult {
  node_voltages: Array<{ node: string; voltage: number }>;
  branch_currents: Array<{ source: string; current: number }>;
}

export interface JoinMetrics {
  n_components: number;
  n_nets: number;
  self_loop_components: number;
  floating_components: number;
  giant_nets: number;
  dangling_wire_ends: number;
  unused_wires: number;
  pct_wires_used: number;
  pct_effective_wires: number;
  pct_connected: number;
  nets_per_component: number;
  composite: number;
  balanced: number;
  join_quality: number;
}

export interface JoinOverlayResult {
  overlay: string; // base64 PNG
  nets: Array<{ net_id: number; pins: number; components: number; wires: number }>;
  metrics: JoinMetrics | null;
  strategy: string;
  warnings: string[];
}

export interface JoinStrategy {
  name: string;
  label: string;
  desc: string;
}

export interface SimOverlayResult {
  overlay: string; // base64 PNG (voltage heatmap)
  available: boolean;
  node_voltages: Array<{ node: string; voltage: number }>;
  branch_currents?: Array<{ source: string; current: number }>;
  vmin?: number;
  vmax?: number;
  n_solved?: number;
  n_nets?: number;
  strategy?: string;
  warnings: string[];
}

export interface HomeInitialData {
  images: string[];
  presets: PresetMap;
  datasets: DatasetMap;
}
