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

/** SSR-safe typed fetch — returns parsed JSON directly. Used by server actions. */
export async function fetchBackend<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} failed (${res.status}): ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}
