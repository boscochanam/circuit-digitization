import { useState, useEffect, useRef } from "react";
import { fetchBackend } from "@/lib/api";
import type { NetlistResult } from "@/lib/types";

interface SimRunResult {
  success: boolean;
  node_voltages?: Array<{ node: string; voltage: number }>;
  branch_currents?: Array<{ source: string; current: number }>;
  error?: string;
}

interface SimulationState {
  loading: boolean;
  error: string | null;
  nodeVoltages: Array<{ node: string; voltage: number }>;
  branchCurrents: Array<{ source: string; current: number }>;
  spiceNetlist: string | null;
}

/**
 * Manages SPICE simulation lifecycle: fetch netlist → run sim → store results.
 * Auto-runs when `enabled` is true (simOverlay === "voltage") and deps change.
 * Re-simulates when componentValues change.
 */
export function useSimulation(
  imageIdx: number,
  dataset: string,
  preset: string,
  params: Record<string, string | number>,
  componentValues: Record<string, string>,
  enabled: boolean,
  strategy: string = "graph_rescue",
  // Re-run the sim when connection-editor overrides change (backend rebuilds the
  // netlist with them).
  overridesKey: string = "",
) {
  const [state, setState] = useState<SimulationState>({
    loading: false,
    error: null,
    nodeVoltages: [],
    branchCurrents: [],
    spiceNetlist: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled) {
      setState({
        loading: false,
        error: null,
        nodeVoltages: [],
        branchCurrents: [],
        spiceNetlist: null,
      });
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState((prev) => ({ ...prev, loading: true, error: null }));

    // Fetch client-side (not via server actions). On image navigation several
    // server actions fire at once and Next serializes them — one can hang and
    // never resolve, freezing the voltage/current readout. Direct fetches
    // (same-origin /api -> backend) with the AbortController always settle.
    fetchBackend<NetlistResult>("/api/netlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        img_idx: imageIdx, ds: dataset, preset, params, strategy,
        ...(Object.keys(componentValues).length > 0 ? { component_values: componentValues } : {}),
      }),
      signal: controller.signal,
    })
      .then((netlist) => {
        if (controller.signal.aborted) return undefined;

        const spice = netlist.spice_netlist;
        setState((prev) => ({ ...prev, spiceNetlist: spice }));

        return fetchBackend<SimRunResult>("/api/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spice_text: spice }),
          signal: controller.signal,
        });
      })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result && result.success) {
          setState((prev) => ({
            loading: false,
            error: null,
            nodeVoltages: result.node_voltages ?? [],
            branchCurrents: result.branch_currents ?? [],
            spiceNetlist: prev.spiceNetlist,
          }));
        } else {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: result?.error ?? "Simulation failed",
          }));
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: err instanceof Error ? err.message : "Simulation failed",
          }));
        }
      });

    return () => {
      controller.abort();
    };
  }, [imageIdx, dataset, preset, params, componentValues, enabled, strategy, overridesKey]);

  return state;
}
