import { create } from "zustand";
import type { PipelineResult, NetlistResult } from "@/lib/types";

// ── Overlay types ──
export type PipelineOverlay = "none" | "source" | "threshold" | "detected" | "dilated";
export type CircuitOverlay = "none" | "components" | "connections" | "values" | "all";
export type SimOverlay = "none" | "voltage" | "current";
export type BottomPanelTab = "netlist" | "warnings" | "raw";

// ── Component entry for sidebar list ──
export interface ComponentEntry {
  name: string;
  type: string;
  value: string;
  position?: { x: number; y: number };
}

// ── Full application state ──
export interface AppState {
  // Image
  imageIdx: number;
  dataset: string;
  imageList: string[];

  // Pipeline
  preset: string;
  params: Record<string, number>;
  pipelineResult: PipelineResult | null;

  // Circuit
  netlist: NetlistResult | null;
  selectedComponent: string | null;
  componentValues: Record<string, string>;

  // Overlays
  pipelineOverlay: PipelineOverlay;
  circuitOverlay: CircuitOverlay;
  simOverlay: SimOverlay;
  joinStrategy: string;

  // UI
  sidebarOpen: boolean;
  bottomPanelOpen: boolean;
  bottomPanelTab: BottomPanelTab;

  // ── Actions ──
  setImageIdx: (idx: number) => void;
  setDataset: (ds: string) => void;
  setImageList: (list: string[]) => void;
  setPreset: (preset: string) => void;
  setParams: (params: Record<string, number>) => void;
  setPipelineResult: (result: PipelineResult | null) => void;
  setNetlist: (netlist: NetlistResult | null) => void;
  setSelectedComponent: (name: string | null) => void;
  setComponentValue: (name: string, value: string) => void;
  setPipelineOverlay: (overlay: PipelineOverlay) => void;
  setCircuitOverlay: (overlay: CircuitOverlay) => void;
  setSimOverlay: (overlay: SimOverlay) => void;
  setJoinStrategy: (strategy: string) => void;
  setSidebarOpen: (open: boolean) => void;
  setBottomPanelOpen: (open: boolean) => void;
  setBottomPanelTab: (tab: BottomPanelTab) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // ── Initial state ──
  imageIdx: 0,
  dataset: "gt_labels",
  imageList: [],

  preset: "best_candidate_v4",
  params: {},
  pipelineResult: null,

  netlist: null,
  selectedComponent: null,
  componentValues: {},

  pipelineOverlay: "none",
  circuitOverlay: "none",
  simOverlay: "none",
  joinStrategy: "graph_rescue",

  sidebarOpen: true,
  bottomPanelOpen: false,
  bottomPanelTab: "netlist",

  // ── Actions ──
  setImageIdx: (imageIdx) => set({ imageIdx }),
  setDataset: (dataset) => set({ dataset }),
  setImageList: (imageList) => set({ imageList }),
  setPreset: (preset) => set({ preset }),
  setParams: (params) => set({ params }),
  setPipelineResult: (pipelineResult) => set({ pipelineResult }),
  setNetlist: (netlist) => set({ netlist }),
  setSelectedComponent: (selectedComponent) => set({ selectedComponent }),
  setComponentValue: (name, value) =>
    set((state) => ({
      componentValues: { ...state.componentValues, [name]: value },
    })),
  setPipelineOverlay: (pipelineOverlay) => set({ pipelineOverlay }),
  setCircuitOverlay: (circuitOverlay) => set({ circuitOverlay }),
  setSimOverlay: (simOverlay) => set({ simOverlay }),
  setJoinStrategy: (joinStrategy) => set({ joinStrategy }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setBottomPanelOpen: (bottomPanelOpen) => set({ bottomPanelOpen }),
  setBottomPanelTab: (bottomPanelTab) => set({ bottomPanelTab }),
}));
