import { useState, useEffect } from "react";
import { fetchBackend } from "@/lib/api";
import type { NetlistResult } from "@/lib/types";

/**
 * Shared netlist hook — deduplicates fetches across NetlistPanel, CircuitGraph,
 * and HomeClient. Caches result by (imageIdx, dataset, preset, params) key.
 */
export function useNetlist(
  imageIdx: number,
  dataset: string,
  preset: string,
  params: Record<string, number>,
  strategy: string = "graph_rescue",
  // Changes when connection-editor overrides change, so the netlist (which the
  // backend rebuilds with those overrides) re-fetches instead of showing stale data.
  overridesKey: string = "",
) {
  const [netlist, setNetlist] = useState<NetlistResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify({ imageIdx, dataset, preset, params, strategy, overridesKey });

  useEffect(() => {
    // Fetch client-side (not via a server action). Several server actions fire at
    // once on image navigation and Next serializes them — one can be left hanging,
    // which left this panel stuck on its loading spinner forever. A direct fetch
    // (same-origin /api is rewritten to the backend) with an AbortController always
    // settles and lets the latest request win.
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetchBackend<NetlistResult>("/api/netlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ img_idx: imageIdx, ds: dataset, preset, params, strategy }),
      signal: controller.signal,
    })
      .then((result) => {
        setNetlist(result);
        setLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Netlist fetch failed");
        setLoading(false);
      });
    return () => controller.abort();
    // `key` is the JSON of every input below, so it captures all the deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { netlist, loading, error };
}
