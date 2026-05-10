const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listImages(ds: string): Promise<string[]> {
  const res = await fetch(`${API}/api/list?ds=${ds}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`listImages failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function fetchDatasets(): Promise<Record<string, { path: string; images: number; sample: string | null }>> {
  const res = await fetch(`${API}/api/datasets`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`fetchDatasets failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function runPipeline(
  imgIdx: number,
  ds: string,
  params: Record<string, string | number>
): Promise<{
  line_count: number;
  blob_count: number;
  elapsed_ms: number;
  overlay: string;
  threshold: string;
  dilated: string;
}> {
  const res = await fetch(`${API}/api/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ img_idx: imgIdx, ds, params }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`runPipeline failed: ${res.status} ${text}`);
  }
  return res.json();
}
