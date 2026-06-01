import type { PipelineResult, PresetMap, DatasetMap, NetlistResult } from "./types";

/** Same-origin /api in the browser (Next rewrites → backend). Direct URL for SSR. */
export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (typeof window !== "undefined") {
    return `${window.location.origin}${p}`;
  }
  const base =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000";
  return `${base.replace(/\/$/, "")}${p}`;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(apiUrl(path), { cache: "no-store", ...init });
}

/** SSR-safe typed fetch — returns parsed JSON directly. */
export async function fetchBackend<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} failed (${res.status}): ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export async function listImages(ds: string): Promise<string[]> {
  const res = await apiFetch(`/api/list?ds=${encodeURIComponent(ds)}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`listImages failed: ${res.status} ${text}`);
  }
  const data = await res.json();
  if (!Array.isArray(data)) {
    throw new Error("listImages: expected JSON array");
  }
  return data;
}

export async function fetchDatasets(): Promise<DatasetMap> {
  const res = await apiFetch("/api/datasets");
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`fetchDatasets failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function fetchPresets(): Promise<PresetMap> {
  const res = await apiFetch("/api/presets");
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`fetchPresets failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function fetchNetlist(
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

export async function runPipeline(
  imgIdx: number,
  ds: string,
  params: Record<string, string | number>,
  preset: string = "legacy_threshold",
): Promise<PipelineResult> {
  const res = await apiFetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx: imgIdx, ds, params, preset }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`runPipeline failed: ${res.status} ${text}`);
  }
  return res.json();
}
