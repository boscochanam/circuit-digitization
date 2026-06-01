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
}

export type PresetMap = Record<
  string,
  { label: string; description: string; params?: Record<string, number> }
>;

export type DatasetMap = Record<
  string,
  { path: string; images: number; sample: string | null }
>;

export interface HomeInitialData {
  images: string[];
  presets: PresetMap;
  datasets: DatasetMap;
}
