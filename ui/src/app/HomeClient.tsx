"use client";

import { useState, useEffect, useCallback } from "react";
import type { HomeInitialData } from "@/lib/types";
import { useImages, type Dataset } from "@/hooks/useImages";
import { usePipeline } from "@/hooks/usePipeline";
import { useSimulation } from "@/hooks/useSimulation";
import { useNetlist } from "@/hooks/useNetlist";
import { fetchSimOverlayAction, fetchCurrentOverlayAction, fetchTopologyAction, fetchPathAction, fetchOverridesAction, saveOverridesAction, clearOverridesAction } from "@/app/actions";
import type { TopologyResult, PathResult, ConnectionOverrides } from "@/lib/types";
import NetlistTab from "@/components/NetlistTab";
import WarningsTab from "@/components/WarningsTab";
import RawTab from "@/components/RawTab";
import { MetricsBar } from "@/components/ui-widgets";
import TopologyGraph from "@/components/TopologyGraph";
import Toolbar from "@/components/Toolbar";
import Sidebar from "@/components/Sidebar";
import CircuitViewport from "@/components/CircuitViewport";
import BottomPanel from "@/components/BottomPanel";
import ImageGrid from "@/components/ImageGrid";
import type { BottomPanelTab } from "@/lib/types";

export default function HomeClient({
  initial,
  initialIdx = 0,
  initialDs = "gt_labels",
}: {
  initial: HomeInitialData;
  initialIdx?: number;
  initialDs?: string;
}) {
  const imgs = useImages(initial, initialIdx, initialDs);
  const pipe = usePipeline(initial, imgs.imageIdx, imgs.dataset, imgs.imageCount);

  // Sync URL query params when navigating images
  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("idx", String(imgs.imageIdx));
    if (imgs.dataset !== "gt_labels") {
      url.searchParams.set("ds", imgs.dataset);
    } else {
      url.searchParams.delete("ds");
    }
    window.history.replaceState(null, "", url.toString());
  }, [imgs.imageIdx, imgs.dataset]);

  const [bottomPanelOpen, setBottomPanelOpen] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [bottomPanelTab, setBottomPanelTab] = useState<BottomPanelTab>("netlist");

  const [componentValues, setComponentValues] = useState<Record<string, string>>({});
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null);

  // The main views (Voltage map + netlist) use the single best join strategy.
  // Lower-level strategy inspection/comparison lives in its own "Join check"
  // view (View bar), which sandboxes any strategy without touching these.
  const joinStrategy = "graph_rescue";

  const handleValueChange = (name: string, value: string) => {
    setComponentValues((prev) => ({ ...prev, [name]: value }));
  };

  // componentValues is keyed by the component name (e.g. "R107"), which is
  // exactly the SPICE device name the backend matches overrides against
  // (spice.py emits `{prefix}{index+1}` and keys value_overrides by that name).
  // So values are sent through as-is — the old name→index conversion sent array
  // indices ("106") that never matched "R107", silently dropping every edit.

  // Voltage overlay state
  const [simOverlayUrl, setSimOverlayUrl] = useState<string | null>(null);
  const [voltageActive, setVoltageActive] = useState(false);

  // Current overlay state
  const [currentOverlayUrl, setCurrentOverlayUrl] = useState<string | null>(null);
  const [currentActive, setCurrentActive] = useState(false);

  // Topology overlay state
  const [topologyActive, setTopologyActive] = useState(false);
  const [topology, setTopology] = useState<TopologyResult | null>(null);
  const [topologyLoading, setTopologyLoading] = useState(false);
  const [topoSelectedNode, setTopoSelectedNode] = useState<number | null>(null);
  const [topoSelectedComponent, setTopoSelectedComponent] = useState<string | null>(null);
  const [showWires, setShowWires] = useState(true);
  const [showPins, setShowPins] = useState(true);
  const [showComponents, setShowComponents] = useState(true);

  // Endpoint selection state
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);

  // Edit mode and overrides state
  const [editMode, setEditMode] = useState<"reassign" | "join" | "disconnect" | null>(null);
  const [joinSource, setJoinSource] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<ConnectionOverrides>({ reassign: {}, join: [], remove: [] });

  const handleEndpointClick = useCallback((endpointKey: string, shiftKey: boolean) => {
    if (shiftKey) {
      // Shift+click reserved for join mode (future)
      return;
    }
    setEditMode(null);
    setSelectedEndpoint((prev) => (prev === endpointKey ? null : endpointKey));
  }, []);

  // Load overrides when image changes
  useEffect(() => {
    fetchOverridesAction(imgs.imageIdx, imgs.dataset)
      .then(setOverrides)
      .catch(() => setOverrides({ reassign: {}, join: [], remove: [] }));
    // Reset edit mode and selections
    setEditMode(null);
    setJoinSource(null);
    setSelectedEndpoint(null);
  }, [imgs.imageIdx, imgs.dataset]);

  // Action handlers for endpoint editing (reassign, join, disconnect)
  const handleReassign = useCallback(async (endpointKey: string, componentName: string, pinName: string) => {
    const newOverrides: ConnectionOverrides = {
      ...overrides,
      reassign: {
        ...overrides.reassign,
        [endpointKey]: { component: componentName, pin: pinName },
      },
    };
    try {
      const updatedTopology = await saveOverridesAction(imgs.imageIdx, imgs.dataset, newOverrides);
      setOverrides(newOverrides);
      setTopology(updatedTopology);
      setEditMode(null);
      setSelectedEndpoint(null);
    } catch (e) {
      console.error("Reassign failed:", e);
    }
  }, [overrides, imgs.imageIdx, imgs.dataset]);

  const handleJoin = useCallback(async (sourceEndpoint: string, targetEndpoint: string) => {
    const newOverrides: ConnectionOverrides = {
      ...overrides,
      join: [...overrides.join, [sourceEndpoint, targetEndpoint]],
    };
    try {
      const updatedTopology = await saveOverridesAction(imgs.imageIdx, imgs.dataset, newOverrides);
      setOverrides(newOverrides);
      setTopology(updatedTopology);
      setEditMode(null);
      setJoinSource(null);
      setSelectedEndpoint(null);
    } catch (e) {
      console.error("Join failed:", e);
    }
  }, [overrides, imgs.imageIdx, imgs.dataset]);

  const handleDisconnect = useCallback(async (endpointKey: string) => {
    const newOverrides: ConnectionOverrides = {
      ...overrides,
      remove: [...overrides.remove, endpointKey],
    };
    try {
      const updatedTopology = await saveOverridesAction(imgs.imageIdx, imgs.dataset, newOverrides);
      setOverrides(newOverrides);
      setTopology(updatedTopology);
      setEditMode(null);
      setSelectedEndpoint(null);
    } catch (e) {
      console.error("Disconnect failed:", e);
    }
  }, [overrides, imgs.imageIdx, imgs.dataset]);

  const handleResetOverrides = useCallback(async () => {
    try {
      const updatedTopology = await clearOverridesAction(imgs.imageIdx, imgs.dataset);
      setOverrides({ reassign: {}, join: [], remove: [] });
      setTopology(updatedTopology);
      setSelectedEndpoint(null);
      setEditMode(null);
    } catch (e) {
      console.error("Reset overrides failed:", e);
    }
  }, [imgs.imageIdx, imgs.dataset]);

  // Path tracing state
  const [pathStart, setPathStart] = useState<string | null>(null);
  const [pathEnd, setPathEnd] = useState<string | null>(null);
  const [pathData, setPathData] = useState<PathResult | null>(null);
  const [pathLoading, setPathLoading] = useState(false);

  const currentParams = pipe.isLegacy ? pipe.params : pipe.presetParams;

  const sim = useSimulation(
    imgs.imageIdx,
    imgs.dataset,
    pipe.preset,
    currentParams,
    componentValues,
    voltageActive,
    joinStrategy,
  );

  const handleRunSimOverlay = useCallback(async () => {
    try {
      const result = await fetchSimOverlayAction(
        imgs.imageIdx,
        imgs.dataset,
        pipe.preset,
        currentParams,
        joinStrategy,
        componentValues,
      );
      if (result.overlay) {
        setSimOverlayUrl(`data:image/png;base64,${result.overlay}`);
      }
    } catch (e) {
      console.error("Sim overlay failed:", e);
    }
  }, [imgs.imageIdx, imgs.dataset, pipe.preset, currentParams, componentValues, joinStrategy]);

  useEffect(() => {
    if (voltageActive) {
      handleRunSimOverlay();
    } else {
      setSimOverlayUrl(null);
    }
  }, [voltageActive, handleRunSimOverlay]);

  // Current overlay fetch
  const handleRunCurrentOverlay = useCallback(async () => {
    try {
      const result = await fetchCurrentOverlayAction(
        imgs.imageIdx,
        imgs.dataset,
        pipe.preset,
        currentParams,
        joinStrategy,
        componentValues,
      );
      if (result.overlay) {
        setCurrentOverlayUrl(`data:image/png;base64,${result.overlay}`);
      }
    } catch (e) {
      console.error("Current overlay failed:", e);
    }
  }, [imgs.imageIdx, imgs.dataset, pipe.preset, currentParams, componentValues, joinStrategy]);

  useEffect(() => {
    if (currentActive) {
      handleRunCurrentOverlay();
    } else {
      setCurrentOverlayUrl(null);
    }
  }, [currentActive, handleRunCurrentOverlay]);

  // Topology fetch
  useEffect(() => {
    if (!topologyActive) {
      setTopology(null);
      setTopoSelectedNode(null);
      setTopoSelectedComponent(null);
      setSelectedEndpoint(null);
      return;
    }
    let cancelled = false;
    setTopologyLoading(true);
    fetchTopologyAction(imgs.imageIdx, imgs.dataset, pipe.preset, currentParams as Record<string, string | number>, joinStrategy)
      .then((result) => {
        if (!cancelled) setTopology(result);
      })
      .catch((e) => {
        console.error("Topology fetch failed:", e);
        if (!cancelled) setTopology(null);
      })
      .finally(() => {
        if (!cancelled) setTopologyLoading(false);
      });
    return () => { cancelled = true; };
  }, [topologyActive, imgs.imageIdx, imgs.dataset, pipe.preset, currentParams, joinStrategy]);

  // Path tracing: fetch path when both start and end are set
  useEffect(() => {
    if (!pathStart || !pathEnd) {
      setPathData(null);
      return;
    }
    if (pathStart === pathEnd) {
      setPathData({ path: [], warnings: ["Start and end components are the same"] });
      return;
    }
    let cancelled = false;
    setPathLoading(true);
    fetchPathAction(
      imgs.imageIdx, imgs.dataset, pipe.preset,
      currentParams as Record<string, string | number>,
      joinStrategy, pathStart, pathEnd,
    )
      .then((result) => { if (!cancelled) setPathData(result); })
      .catch((e) => { console.error("Path fetch failed:", e); if (!cancelled) setPathData(null); })
      .finally(() => { if (!cancelled) setPathLoading(false); });
    return () => { cancelled = true; };
  }, [pathStart, pathEnd, imgs.imageIdx, imgs.dataset, pipe.preset, currentParams, joinStrategy]);

  // Clear path when image changes
  useEffect(() => {
    setPathStart(null);
    setPathEnd(null);
    setPathData(null);
  }, [imgs.imageIdx, imgs.dataset]);

  const { netlist: netlistData, loading: netlistLoading, error: netlistError } = useNetlist(
    imgs.imageIdx,
    imgs.dataset,
    pipe.preset,
    currentParams as Record<string, number>,
    joinStrategy,
  );

  const componentList = (pipe.result?.components ?? []).map((c) => ({
    name: c.name,
    type: String.fromCharCode(65 + c.class_id) ?? "?",
    value: componentValues[c.name] ?? "",
    position: c.bbox ? { x: (c.bbox[0] + c.bbox[2]) / 2, y: (c.bbox[1] + c.bbox[3]) / 2 } : undefined,
  }));

  const handleOverlayChange = (overlay: string) => {
    setVoltageActive(overlay === "voltage");
    setCurrentActive(overlay === "current");
    setTopologyActive(overlay === "topology");
  };

  // Handle shift+click for path selection (called from CircuitViewport)
  const handlePathClick = useCallback((name: string) => {
    if (!pathStart) {
      setPathStart(name);
      setPathEnd(null);
      setPathData(null);
    } else if (!pathEnd) {
      if (name === pathStart) {
        // Clicking same component clears path
        setPathStart(null);
        setPathEnd(null);
        setPathData(null);
      } else {
        setPathEnd(name);
      }
    } else {
      // Both set, start new selection
      setPathStart(name);
      setPathEnd(null);
      setPathData(null);
    }
  }, [pathStart, pathEnd]);

  const [ocrResults, setOcrResults] = useState<any>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  // Surface OCR outcome instead of failing silently (no API key / no labels / etc.)
  const [ocrStatus, setOcrStatus] = useState<{ kind: "success" | "error" | "info"; msg: string } | null>(null);

  useEffect(() => {
    if (!ocrStatus) return;
    const t = setTimeout(() => setOcrStatus(null), 7000);
    return () => clearTimeout(t);
  }, [ocrStatus]);

  const handleRunOCR = async () => {
    setOcrLoading(true);
    setOcrStatus(null);
    try {
      const res = await fetch("/api/ocr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_idx: imgs.imageIdx,
          dataset: imgs.dataset,
        }),
      });
      const data = await res.json();
      setOcrResults(data);

      if (data?.error) {
        // Don't swallow it — tell the user the actual reason and what to do.
        const msg = /OPENROUTER_API_KEY/i.test(data.error)
          ? "OCR needs an OPENROUTER_API_KEY set on the backend to read values."
          : data.error;
        setOcrStatus({ kind: "error", msg });
        return;
      }

      let filled = 0;
      if (data?.components && pipe.result?.components) {
        const newValues: Record<string, string> = {};
        for (const ocrComp of data.components) {
          if (ocrComp.type === "text" && ocrComp.value) {
            const matchIdx: number = pipe.result.components.findIndex(
              (c: any, idx: number) => Math.abs(idx - ocrComp.index) < 5
            );
            if (matchIdx >= 0) {
              const compName = pipe.result.components[matchIdx].name;
              if (!componentValues[compName]) {
                newValues[compName] = ocrComp.value;
              }
            }
          }
        }
        filled = Object.keys(newValues).length;
        if (filled > 0) {
          setComponentValues((prev) => ({ ...prev, ...newValues }));
        }
      }
      setOcrStatus(
        filled > 0
          ? { kind: "success", msg: `Read ${filled} value${filled === 1 ? "" : "s"} from the schematic — see the Values tab.` }
          : { kind: "info", msg: "OCR ran, but found no printed values to fill." },
      );
    } catch (e) {
      console.error("OCR failed:", e);
      setOcrStatus({ kind: "error", msg: "OCR request failed — is the backend running?" });
    } finally {
      setOcrLoading(false);
    }
  };

  const sourceImageUrl = imgs.imageList.length > 0
    ? `/api/thumb?idx=${imgs.imageIdx}&ds=${imgs.dataset}`
    : undefined;

  return (
    <div className="app-shell">
      <header className="header">
        <h1 className="header-title">WIRE DETECTION TUNER</h1>
        <span className="header-badge">v0.833</span>
      </header>

      {ocrStatus && (
        <div className={`ocr-toast ocr-toast-${ocrStatus.kind}`} role="status">
          <span className="ocr-toast-msg">{ocrStatus.msg}</span>
          <button className="ocr-toast-x" aria-label="Dismiss" onClick={() => setOcrStatus(null)}>✕</button>
        </div>
      )}

      <Toolbar
        imageIdx={imgs.imageIdx}
        imageCount={imgs.imageCount}
        dataset={imgs.dataset}
        preset={pipe.preset}
        onPrev={() => imgs.setImageIdx(Math.max(0, imgs.imageIdx - 1))}
        onNext={() => imgs.setImageIdx(Math.min(imgs.imageCount - 1, imgs.imageIdx + 1))}
        onDatasetChange={(ds) => imgs.setDataset(ds as Dataset)}
        onPresetChange={pipe.setPreset}
        presets={pipe.presets}
        showGrid={showGrid}
        onToggleGrid={() => setShowGrid(!showGrid)}
      />

      {showGrid && (
        <ImageGrid
          imageList={imgs.imageList}
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          gridCount={imgs.gridCount}
          onSelect={(i) => { imgs.setImageIdx(i); setShowGrid(false); }}
          onScroll={imgs.handleGridScroll}
          onClose={() => setShowGrid(false)}
        />
      )}

      <MetricsBar result={pipe.result} preset={pipe.preset} />

      <div className="desktop-layout">
        <Sidebar
          presetParams={pipe.presetParams}
          onPresetParamChange={pipe.setPresetParam}
          isLegacy={pipe.isLegacy}
          legacyParams={pipe.params}
          onLegacyParamChange={(key, val) => pipe.setParam(key, val)}
          preset={pipe.preset}
          presets={pipe.presets}
          onPresetChange={pipe.setPreset}
          components={componentList}
          selectedComponent={selectedComponent}
          onComponentSelect={setSelectedComponent}
          onComponentValueChange={handleValueChange}
        />

        <CircuitViewport
          sourceImageUrl={sourceImageUrl}
          pipelineResult={pipe.result}
          simOverlayUrl={simOverlayUrl}
          currentOverlayUrl={currentOverlayUrl}
          ocrResults={ocrResults}
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          preset={pipe.preset}
          params={currentParams}
          onRunOCR={handleRunOCR}
          ocrLoading={ocrLoading}
          onActiveOverlayChange={handleOverlayChange}
          componentValues={componentValues}
          onValueChange={handleValueChange}
          topology={topology}
          topologyLoading={topologyLoading}
          selectedNode={topoSelectedNode}
          selectedComponent={topoSelectedComponent}
          onNodeSelect={setTopoSelectedNode}
          onComponentSelect={setTopoSelectedComponent}
          pathStart={pathStart}
          pathEnd={pathEnd}
          pathData={pathData}
          onPathClick={handlePathClick}
          showWires={showWires}
          showPins={showPins}
          showComponents={showComponents}
          onToggleWires={() => setShowWires((v) => !v)}
          onTogglePins={() => setShowPins((v) => !v)}
          onToggleComponents={() => setShowComponents((v) => !v)}
          selectedEndpoint={selectedEndpoint}
          onEndpointClick={handleEndpointClick}
          onEndpointClear={() => setSelectedEndpoint(null)}
          editMode={editMode}
          onSetEditMode={setEditMode}
          joinSource={joinSource}
          onSetJoinSource={setJoinSource}
          overrides={overrides}
          onReassign={handleReassign}
          onJoin={handleJoin}
          onDisconnect={handleDisconnect}
          onResetOverrides={handleResetOverrides}
        />
      </div>

      <BottomPanel
        activeTab={bottomPanelTab}
        onTabChange={(tab) => setBottomPanelTab(tab as BottomPanelTab)}
        isOpen={bottomPanelOpen}
        onToggle={() => setBottomPanelOpen(!bottomPanelOpen)}
      >
        {bottomPanelTab === "netlist" && (
          <NetlistTab
            netlist={netlistData}
            spiceNetlist={sim.spiceNetlist}
            loading={netlistLoading || sim.loading}
            error={netlistError ?? sim.error}
          />
        )}
        {bottomPanelTab === "warnings" && (
          <WarningsTab netlist={netlistData} loading={netlistLoading} />
        )}
        {bottomPanelTab === "raw" && (
          <RawTab result={pipe.result} />
        )}
        {bottomPanelTab === "graph" && topology && (
          <TopologyGraph
            topology={topology}
            selectedNode={topoSelectedNode}
            selectedComponent={topoSelectedComponent}
            onNodeSelect={setTopoSelectedNode}
            onComponentSelect={setTopoSelectedComponent}
            pathStart={pathStart}
            pathEnd={pathEnd}
            pathData={pathData}
            onPathClick={handlePathClick}
          />
        )}
      </BottomPanel>

      <div className="status-bar">
        <span className="status-live">● LIVE</span>
        <span>{imgs.imageList.length} imgs</span>
        <span>{pipe.preset}</span>
      </div>
    </div>
  );
}
