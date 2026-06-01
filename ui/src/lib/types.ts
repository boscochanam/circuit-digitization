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

export interface HomeInitialData {
  images: string[];
  presets: PresetMap;
  datasets: DatasetMap;
}
