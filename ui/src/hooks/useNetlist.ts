import { useState, useEffect, useRef } from "react";
import { fetchNetlistAction } from "@/app/actions";
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
  const fetchIdRef = useRef(0);

  const key = JSON.stringify({ imageIdx, dataset, preset, params, strategy, overridesKey });
  // start empty so the FIRST run fetches (previously seeded with `key`, which made
  // the mount effect early-return → the netlist panel never loaded until a change).
  const prevKeyRef = useRef<string>("");

  useEffect(() => {
    if (key === prevKeyRef.current) return;
    prevKeyRef.current = key;

    const id = ++fetchIdRef.current;
    setLoading(true);
    setError(null);

    fetchNetlistAction(imageIdx, dataset, preset, params, undefined, strategy)
      .then((result) => {
        if (id === fetchIdRef.current) {
          setNetlist(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (id === fetchIdRef.current) {
          setError(err instanceof Error ? err.message : "Netlist fetch failed");
          setLoading(false);
        }
      });
  }, [key, imageIdx, dataset, preset, params, strategy, overridesKey]);

  return { netlist, loading, error };
}
