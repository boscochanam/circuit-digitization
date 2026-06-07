import { useState, useEffect, useRef } from "react";
import { fetchNetlistAction, runSimulationAction } from "@/app/actions";

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

    fetchNetlistAction(imageIdx, dataset, preset, params)
      .then((netlist) => {
        if (controller.signal.aborted) return undefined;

        const spice = netlist.spice_netlist;
        setState((prev) => ({ ...prev, spiceNetlist: spice }));

        return runSimulationAction(spice);
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
  }, [imageIdx, dataset, preset, params, componentValues, enabled]);

  return state;
}
