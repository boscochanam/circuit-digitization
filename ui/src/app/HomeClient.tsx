"use client";

import { useState, useEffect, useCallback } from "react";
import type { HomeInitialData } from "@/lib/types";
import { useImages, type Dataset } from "@/hooks/useImages";
import { usePipeline } from "@/hooks/usePipeline";
import { useSimulation } from "@/hooks/useSimulation";
import { useNetlist } from "@/hooks/useNetlist";
import { fetchSimOverlayAction } from "@/app/actions";
import NetlistTab from "@/components/NetlistTab";
import WarningsTab from "@/components/WarningsTab";
import RawTab from "@/components/RawTab";
import { MetricsBar } from "@/components/ui-widgets";
import Toolbar from "@/components/Toolbar";
import Sidebar from "@/components/Sidebar";
import CircuitViewport from "@/components/CircuitViewport";
import BottomPanel from "@/components/BottomPanel";
import ImageGrid from "@/components/ImageGrid";
import type { BottomPanelTab } from "@/stores/appStore";

export default function HomeClient({ initial }: { initial: HomeInitialData }) {
  const imgs = useImages(initial);
  const pipe = usePipeline(initial, imgs.imageIdx, imgs.dataset, imgs.imageCount);

  const [bottomPanelOpen, setBottomPanelOpen] = useState(true);
  const [showGrid, setShowGrid] = useState(false);
  const [bottomPanelTab, setBottomPanelTab] = useState<BottomPanelTab>("netlist");

  const [componentValues, setComponentValues] = useState<Record<string, string>>({});
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null);

  const handleValueChange = (name: string, value: string) => {
    setComponentValues((prev) => ({ ...prev, [name]: value }));
  };

  // Voltage overlay state
  const [simOverlayUrl, setSimOverlayUrl] = useState<string | null>(null);
  const [voltageActive, setVoltageActive] = useState(false);

  const currentParams = pipe.isLegacy ? pipe.params : pipe.presetParams;

  const sim = useSimulation(
    imgs.imageIdx,
    imgs.dataset,
    pipe.preset,
    currentParams,
    componentValues,
    voltageActive,
  );

  const handleRunSimOverlay = useCallback(async () => {
    try {
      const result = await fetchSimOverlayAction(
        imgs.imageIdx,
        imgs.dataset,
        pipe.preset,
        currentParams,
        "graph_rescue",
      );
      if (result.overlay) {
        setSimOverlayUrl(`data:image/png;base64,${result.overlay}`);
      }
    } catch (e) {
      console.error("Sim overlay failed:", e);
    }
  }, [imgs.imageIdx, imgs.dataset, pipe.preset, currentParams]);

  useEffect(() => {
    if (voltageActive) {
      handleRunSimOverlay();
    } else {
      setSimOverlayUrl(null);
    }
  }, [voltageActive, handleRunSimOverlay]);

  const { netlist: netlistData, loading: netlistLoading, error: netlistError } = useNetlist(
    imgs.imageIdx,
    imgs.dataset,
    pipe.preset,
    currentParams as Record<string, number>,
  );

  const componentList = (pipe.result?.components ?? []).map((c) => ({
    name: c.name,
    type: String.fromCharCode(65 + c.class_id) ?? "?",
    value: componentValues[c.name] ?? "",
    position: c.bbox ? { x: (c.bbox[0] + c.bbox[2]) / 2, y: (c.bbox[1] + c.bbox[3]) / 2 } : undefined,
  }));

  const handleOverlayChange = (overlay: string) => {
    setVoltageActive(overlay === "voltage");
  };

  const [ocrResults, setOcrResults] = useState<any>(null);
  const [ocrLoading, setOcrLoading] = useState(false);

  const handleRunOCR = async () => {
    setOcrLoading(true);
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
        if (Object.keys(newValues).length > 0) {
          setComponentValues((prev) => ({ ...prev, ...newValues }));
        }
      }
    } catch (e) {
      console.error("OCR failed:", e);
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
      </BottomPanel>

      <div className="status-bar">
        <span className="status-live">● LIVE</span>
        <span>{imgs.imageList.length} imgs</span>
        <span>{pipe.preset}</span>
      </div>
    </div>
  );
}
