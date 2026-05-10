const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listImages(ds: string): Promise<string[]> {
  const res = await fetch(`${API}/api/list?ds=${ds}`);
  return res.json();
}

export async function getThumbnail(idx: number, ds: string): Promise<{ image: string; index: number }> {
  const res = await fetch(`${API}/api/thumb?idx=${idx}&ds=${ds}`);
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
  return res.json();
}
