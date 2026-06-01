"use server";

import { fetchBackend } from "@/lib/api";
import type { PipelineResult, PresetMap, DatasetMap, NetlistResult } from "@/lib/types";

export type { PresetMap, DatasetMap };

export async function listImagesAction(ds: string): Promise<string[]> {
  const data = await fetchBackend<string[]>(`/api/list?ds=${encodeURIComponent(ds)}`);
  if (!Array.isArray(data)) throw new Error("listImages: expected array");
  return data;
}

export async function fetchDatasetsAction(): Promise<DatasetMap> {
  return fetchBackend<DatasetMap>("/api/datasets");
}

export async function fetchPresetsAction(): Promise<PresetMap> {
  return fetchBackend<PresetMap>("/api/presets");
}

export async function fetchNetlistAction(
  imgIdx: number,
  ds: string,
  preset: string,
): Promise<NetlistResult> {
  return fetchBackend("/api/netlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx: imgIdx, ds, preset }),
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
