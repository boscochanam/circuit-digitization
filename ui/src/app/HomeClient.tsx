"use client";

import { useState } from "react";
import type { HomeInitialData } from "@/lib/types";
import { useImages, type Dataset } from "@/hooks/useImages";
import { usePipeline } from "@/hooks/usePipeline";
import { useSimulation } from "@/hooks/useSimulation";
import { useNetlist } from "@/hooks/useNetlist";
import NetlistTab from "@/components/NetlistTab";
import WarningsTab from "@/components/WarningsTab";
import RawTab from "@/components/RawTab";
import { MetricsBar } from "@/components/ui-widgets";
import Toolbar from "@/components/Toolbar";
import Sidebar from "@/components/Sidebar";
import CircuitViewport from "@/components/CircuitViewport";
import BottomPanel from "@/components/BottomPanel";
import type { BottomPanelTab } from "@/stores/appStore";

export default function HomeClient({ initial }: { initial: HomeInitialData }) {
  const imgs = useImages(initial);
  const pipe = usePipeline(initial, imgs.imageIdx, imgs.dataset, imgs.imageCount);

  const [bottomPanelOpen, setBottomPanelOpen] = useState(true);
  const [bottomPanelTab, setBottomPanelTab] = useState<BottomPanelTab>("netlist");

  const [componentValues, setComponentValues] = useState<Record<string, string>>({});
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null);

  const handleValueChange = (name: string, value: string) => {
    setComponentValues((prev) => ({ ...prev, [name]: value }));
  };

  const currentParams = pipe.isLegacy ? pipe.params : pipe.presetParams;

  const sim = useSimulation(
    imgs.imageIdx,
    imgs.dataset,
    pipe.preset,
    currentParams,
    componentValues,
    false,
  );

  const { netlist: netlistData, loading: netlistLoading, error: netlistError } = useNetlist(
    imgs.imageIdx,
    imgs.dataset,
    pipe.preset,
    currentParams as Record<string, number>,
  );

  const componentList = (pipe.result?.components ?? []).map((c) => ({
    name: c.name,
    type: String.fromCharCode(65 + c.class_id) || "?",
    value: componentValues[c.name] ?? "",
    position: c.bbox ? { x: (c.bbox[0] + c.bbox[2]) / 2, y: (c.bbox[1] + c.bbox[3]) / 2 } : undefined,
  }));

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
      />

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
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          preset={pipe.preset}
          params={currentParams}
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
