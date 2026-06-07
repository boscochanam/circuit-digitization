"use server";

import { fetchBackend } from "@/lib/api";
import type { PipelineResult, NetlistResult, JoinOverlayResult, JoinStrategy, SimOverlayResult } from "@/lib/types";

export async function listImagesAction(ds: string): Promise<string[]> {
  const data = await fetchBackend<string[]>(`/api/list?ds=${encodeURIComponent(ds)}`);
  if (!Array.isArray(data)) throw new Error("listImages: expected array");
  return data;
}

export async function fetchDatasetsAction(): Promise<Record<string, { path: string; images: number; sample: string | null }>> {
  return fetchBackend("/api/datasets");
}

export async function fetchPresetsAction(): Promise<Record<string, { label: string; description: string; params?: Record<string, number> }>> {
  return fetchBackend("/api/presets");
}

export async function fetchNetlistAction(
  imgIdx: number,
  ds: string,
  preset: string,
  params: Record<string, string | number> = {},
  componentValues?: Record<string, string>,
): Promise<NetlistResult> {
  return fetchBackend("/api/netlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      img_idx: imgIdx,
      ds,
      preset,
      params,
      ...(componentValues && Object.keys(componentValues).length > 0
        ? { component_values: componentValues }
        : {}),
    }),
  });
}

export async function runSimulationAction(
  spiceText: string,
): Promise<{
  success: boolean;
  node_voltages: Array<{ node: string; voltage: number }>;
  branch_currents: Array<{ source: string; current: number }>;
  error?: string;
}> {
  return fetchBackend("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spice_text: spiceText }),
  });
}

export async function fetchJoinOverlayAction(
  imgIdx: number,
  ds: string,
  preset: string,
  params: Record<string, string | number> = {},
  net: number | null = null,
  strategy: string | null = null,
): Promise<JoinOverlayResult> {
  return fetchBackend("/api/join_overlay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx: imgIdx, ds, preset, params, net, strategy }),
  });
}

export async function fetchJoinStrategiesAction(): Promise<{ strategies: JoinStrategy[]; default: string }> {
  return fetchBackend("/api/join_strategies");
}

export async function fetchSimOverlayAction(
  imgIdx: number,
  ds: string,
  preset: string,
  params: Record<string, string | number> = {},
  strategy: string | null = null,
): Promise<SimOverlayResult> {
  return fetchBackend("/api/sim_overlay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx: imgIdx, ds, preset, params, strategy }),
  });
}

export async function runPipelineAction(
  imgIdx: number,
  ds: string,
  params: Record<string, string | number>,
  preset: string,
): Promise<PipelineResult> {
  return fetchBackend("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx: imgIdx, ds, params, preset }),
  });
}
