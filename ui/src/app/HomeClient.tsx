"use client";

import { useState, useRef } from "react";
import type { HomeInitialData } from "@/lib/types";
import { useImages } from "@/hooks/useImages";
import { usePipeline } from "@/hooks/usePipeline";
import NetlistPanel from "@/components/NetlistPanel";
import SimulationPanel from "@/components/SimulationPanel";
import CircuitGraph from "@/components/CircuitGraph";
import JoinCheckPanel from "@/components/JoinCheckPanel";
import VoltageMapPanel from "@/components/VoltageMapPanel";
import {
  MetricsBar,
  PanelTabs,
  ImageViewport,
  ImageGrid,
  SidebarSection,
  ParamGroup,
  ParamSlider,
  ImagePanel,
} from "@/components/ui-widgets";
import { fetchNetlistAction, runSimulationAction } from "@/app/actions";

const DATASETS = ["gt_labels", "hdc", "synthetic"] as const;
const DATASET_LABELS: Record<string, string> = {
  gt_labels: "GT Labels",
  hdc: "HDC (1680)",
  synthetic: "Synthetic",
};
const IMAGE_PANELS = ["Detected Lines", "Threshold", "Dilated / Closed", "Source", "Netlist", "Simulation", "Topology", "Join Check", "Voltage Map"] as const;

export default function HomeClient({ initial }: { initial: HomeInitialData }) {
  const imgs = useImages(initial);
  const pipe = usePipeline(initial, imgs.imageIdx, imgs.dataset, imgs.imageCount);

  const [preview, setPreview] = useState<{ title: string; image: string } | null>(null);
  const [activePanel, setActivePanel] = useState(0);
  const [sheetOpen, setSheetOpen] = useState(false);
  const sheetRef = useRef<HTMLDivElement>(null);
  const sheetStartY = useRef(0);
  const sheetCurrentY = useRef(0);

  // Swipe handlers for image panels
  const touchStartX = useRef(0);
  const handlePanelTouchStart = (e: React.TouchEvent) => { touchStartX.current = e.touches[0].clientX; };
  const handlePanelTouchEnd = (e: React.TouchEvent) => {
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 50) {
      if (dx < 0 && activePanel < 8) setActivePanel((p) => p + 1);
      if (dx > 0 && activePanel > 0) setActivePanel((p) => p - 1);
    }
  };

  // Bottom sheet drag handlers
  const handleSheetTouchStart = (e: React.TouchEvent) => { sheetStartY.current = e.touches[0].clientY; };
  const handleSheetTouchMove = (e: React.TouchEvent) => {
    sheetCurrentY.current = e.touches[0].clientY;
    const dy = sheetCurrentY.current - sheetStartY.current;
    if (sheetRef.current) {
      if (dy > 0) sheetRef.current.style.transform = `translateY(${dy}px)`;
    }
  };
  const handleSheetTouchEnd = () => {
    const dy = sheetCurrentY.current - sheetStartY.current;
    if (dy > 80) setSheetOpen(false);
    if (sheetRef.current) sheetRef.current.style.transform = "";
  };

  const thumbSrc =
    imgs.imageList.length > 0 ? `/api/thumb?idx=${imgs.imageIdx}&ds=${imgs.dataset}` : undefined;

  const getPanelImage = (panelIdx: number): { base64?: string; src?: string } => {
    const thumb = thumbSrc ? { src: thumbSrc } : {};
    switch (panelIdx) {
      case 0: return pipe.result?.overlay ? { base64: pipe.result.overlay } : thumb;
      case 1: return pipe.result?.threshold ? { base64: pipe.result.threshold } : thumb;
      case 2: return pipe.result?.dilated ? { base64: pipe.result.dilated } : thumb;
      case 3: return thumb;
      default: return {};
    }
  };

  const isNetlistPanel = activePanel === 4;
  const isSimulationPanel = activePanel === 5;
  const isTopologyPanel = activePanel === 6;
  const isJoinPanel = activePanel === 7;
  const isVoltPanel = activePanel === 8;

  const currentParams = pipe.isLegacy ? pipe.params : pipe.presetParams;

  const panelImage = getPanelImage(activePanel);
  const panelTitle = IMAGE_PANELS[activePanel];

  return (
    <>
    <div className="app-shell">
      {/* ═══ HEADER ═══ */}
      <header className="header">
        <div className="header-left">
          <button className="header-menu-btn" onClick={() => setSheetOpen(!sheetOpen)} aria-label="Toggle controls">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="2" strokeLinecap="square"/></svg>
          </button>
          <h1 className="header-title">WIRE DETECTION TUNER</h1>
        </div>
        <span className="header-badge">v0.833</span>
      </header>

      <MetricsBar result={pipe.result} preset={pipe.preset} />

      {/* ═══ IMAGE VIEWPORT / NETLIST / SIMULATION / GRID ═══ */}
      {imgs.viewMode === "single" && isNetlistPanel ? (
        <NetlistPanel
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          preset={pipe.preset}
          params={currentParams}
        />
      ) : imgs.viewMode === "single" && isSimulationPanel ? (
        <SimulationPanel
          onRunSimulation={async () => {
            const netlist = await fetchNetlistAction(imgs.imageIdx, imgs.dataset, pipe.preset, currentParams);
            return runSimulationAction(netlist.spice_netlist);
          }}
        />
      ) : imgs.viewMode === "single" && isTopologyPanel ? (
        <CircuitGraph
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          preset={pipe.preset}
          params={currentParams}
        />
      ) : imgs.viewMode === "single" && isJoinPanel ? (
        <JoinCheckPanel
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          preset={pipe.preset}
          params={currentParams}
        />
      ) : imgs.viewMode === "single" && isVoltPanel ? (
        <VoltageMapPanel
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          preset={pipe.preset}
          params={currentParams}
        />
      ) : imgs.viewMode === "single" ? (
        <ImageViewport
          panelImage={panelImage}
          panelTitle={panelTitle}
          loading={pipe.loading}
          listLoading={imgs.listLoading}
          listError={imgs.listError}
          pipelineError={pipe.pipelineError}
          imageList={imgs.imageList}
          imageIdx={imgs.imageIdx}
          onPrev={() => imgs.setImageIdx(Math.max(0, imgs.imageIdx - 1))}
          onNext={() => imgs.setImageIdx(Math.min(imgs.imageList.length - 1, imgs.imageIdx + 1))}
          onGrid={() => imgs.setViewMode("grid")}
          onTouchStart={handlePanelTouchStart}
          onTouchEnd={handlePanelTouchEnd}
        />
      ) : (
        <ImageGrid
          imageList={imgs.imageList}
          imageIdx={imgs.imageIdx}
          dataset={imgs.dataset}
          gridCount={imgs.gridCount}
          gridScrollRef={imgs.gridScrollRef}
          onScroll={imgs.handleGridScroll}
          onSelect={(i) => { imgs.setImageIdx(i); imgs.setViewMode("single"); }}
        />
      )}

      <PanelTabs panels={IMAGE_PANELS} activePanel={activePanel} onSelect={setActivePanel} />

      {/* ═══ DESKTOP PANEL TABS (hidden on mobile) — only Netlist, Simulation, Topology ═══ */}
      <div className="desktop-tab-bar">
        {IMAGE_PANELS.slice(4).map((name, i) => (
          <button
            key={name}
            className={`desktop-tab ${i + 4 === activePanel ? "desktop-tab-active" : ""}`}
            onClick={() => setActivePanel(i + 4)}
          >
            {name}
          </button>
        ))}
      </div>

      {/* ═══ DESKTOP CONTENT (hidden on mobile) ═══ */}
      <div className="desktop-grid">
        {/* 4-panel image grid always visible */}
        <div className="desktop-image-grid">
          <ImagePanel title="Detected Lines" base64={pipe.result?.overlay} loading={pipe.loading} error={pipe.pipelineError} onClick={() => pipe.result?.overlay && setPreview({ title: "Detected Lines", image: `data:image/jpeg;base64,${pipe.result.overlay}` })} />
          <ImagePanel title="Threshold" base64={pipe.result?.threshold} loading={pipe.loading} error={pipe.pipelineError} onClick={() => pipe.result?.threshold && setPreview({ title: "Threshold", image: `data:image/jpeg;base64,${pipe.result.threshold}` })} />
          <ImagePanel title="Dilated / Closed" base64={pipe.result?.dilated} loading={pipe.loading} error={pipe.pipelineError} onClick={() => pipe.result?.dilated && setPreview({ title: "Dilated", image: `data:image/jpeg;base64,${pipe.result.dilated}` })} />
          <ImagePanel title="Source" src={`/api/thumb?idx=${imgs.imageIdx}&ds=${imgs.dataset}`} onClick={() => setPreview({ title: "Source", image: `/api/thumb?idx=${imgs.imageIdx}&ds=${imgs.dataset}` })} />
        </div>
        {pipe.result?.params && (
          <div className="desktop-params-strip">
            {Object.entries(pipe.result.params).map(([k, v]) => (
              <span key={k}>{k}: <strong>{String(v)}</strong></span>
            ))}
          </div>
        )}
        <div className="desktop-bottom-panel">
          {activePanel === 4 ? (
            <NetlistPanel
              imageIdx={imgs.imageIdx}
              dataset={imgs.dataset}
              preset={pipe.preset}
              params={currentParams}
            />
          ) : activePanel === 5 ? (
            <SimulationPanel
              onRunSimulation={async () => {
                const netlist = await fetchNetlistAction(imgs.imageIdx, imgs.dataset, pipe.preset, currentParams);
                return runSimulationAction(netlist.spice_netlist);
              }}
            />
          ) : activePanel === 6 ? (
            <div className="desktop-split">
              <div className="desktop-split-image">
                <ImagePanel
                  title="Detected Lines"
                  base64={pipe.result?.overlay}
                  loading={pipe.loading}
                  error={pipe.pipelineError}
                />
              </div>
              <div className="desktop-split-graph">
                <CircuitGraph
                  imageIdx={imgs.imageIdx}
                  dataset={imgs.dataset}
                  preset={pipe.preset}
                  params={currentParams}
                />
              </div>
            </div>
          ) : activePanel === 7 ? (
            <JoinCheckPanel
              imageIdx={imgs.imageIdx}
              dataset={imgs.dataset}
              preset={pipe.preset}
              params={currentParams}
            />
          ) : activePanel === 8 ? (
            <VoltageMapPanel
              imageIdx={imgs.imageIdx}
              dataset={imgs.dataset}
              preset={pipe.preset}
              params={currentParams}
            />
          ) : null}
        </div>
      </div>

      {/* ═══ DESKTOP SIDEBAR (hidden on mobile) ═══ */}
      <aside className="sidebar">
        <SidebarSection label="Pipeline Preset">
          <select value={pipe.preset} onChange={(e) => pipe.setPreset(e.target.value)} className="preset-select">
            {Object.entries(pipe.presets).map(([key, p]) => (
              <option key={key} value={key}>{p.label}</option>
            ))}
          </select>
          {pipe.presets[pipe.preset]?.description && (
            <div className="preset-desc">{pipe.presets[pipe.preset].description}</div>
          )}
        </SidebarSection>

        <SidebarSection label="Dataset">
          <div className="dataset-toggle">
            {DATASETS.map((d, i) => (
              <button key={d} onClick={() => imgs.setDataset(d)} className={`dataset-btn ${imgs.dataset === d ? "dataset-btn-active" : ""}`} style={{ borderLeft: i > 0 ? "none" : undefined }}>
                {DATASET_LABELS[d] ?? d}
              </button>
            ))}
          </div>
        </SidebarSection>

        <SidebarSection label="Current Image">
          {imgs.listError && (
            <div className="preset-desc" style={{ color: "var(--error)", marginBottom: 8 }}>{imgs.listError}</div>
          )}
          <button
            onClick={() => imgs.setPickerOpen(true)}
            disabled={imgs.listLoading || imgs.imageCount === 0}
            className="image-picker-btn"
          >
            {imgs.listLoading ? (
              "LOADING..."
            ) : imgs.imageCount > 0 ? (
              <img src={`/api/thumb?idx=${imgs.imageIdx}&ds=${imgs.dataset}`} alt="" className="image-picker-thumb" />
            ) : (
              "NO IMAGES"
            )}
          </button>
          {imgs.imageCount > 0 && (
            <div className="image-nav" style={{ marginTop: 8 }}>
              <button
                className="image-nav-btn"
                onClick={() => imgs.setImageIdx(Math.max(0, imgs.imageIdx - 1))}
                disabled={imgs.imageIdx === 0}
                aria-label="Previous image"
              >←</button>
              <span className="image-nav-count">
                {imgs.imageIdx + 1} / {imgs.imageCount}
                {imgs.imageList.length === 0 && imgs.datasetInfo[imgs.dataset]?.images ? " (index only)" : ""}
              </span>
              <button
                className="image-nav-btn"
                onClick={() => imgs.setImageIdx(Math.min(imgs.imageCount - 1, imgs.imageIdx + 1))}
                disabled={imgs.imageIdx >= imgs.imageCount - 1}
                aria-label="Next image"
              >→</button>
            </div>
          )}
        </SidebarSection>

        <SidebarSection label="Parameters">
          {!pipe.isLegacy ? (
            <>
              <ParamGroup title="Thresholding">
                <ParamSlider label="Sauvola k" value={pipe.presetParams.sauvola_k ?? 0.285} min={0.05} max={0.6} step={0.005} onChange={(v) => pipe.setPresetParam("sauvola_k", v)} />
                <ParamSlider label="Window" value={pipe.presetParams.sauvola_window ?? 67} min={3} max={151} step={2} onChange={(v) => pipe.setPresetParam("sauvola_window", v)} />
                <ParamSlider label="Close Kernel" value={pipe.presetParams.close_kernel ?? 3} min={1} max={15} step={2} onChange={(v) => pipe.setPresetParam("close_kernel", v)} />
              </ParamGroup>
              <ParamGroup title="Component Filtering">
                <ParamSlider label="CCL Min Area" value={pipe.presetParams.ccl_min_area ?? 28} min={0} max={100} step={1} onChange={(v) => pipe.setPresetParam("ccl_min_area", v)} />
              </ParamGroup>
              <ParamGroup title="Deduplication">
                <ParamSlider label="Angle" value={pipe.presetParams.dedup_angle ?? 10} min={0} max={45} step={1} unit="°" onChange={(v) => pipe.setPresetParam("dedup_angle", v)} />
                <ParamSlider label="Distance" value={pipe.presetParams.dedup_dist ?? 18} min={0} max={50} step={1} unit="px" onChange={(v) => pipe.setPresetParam("dedup_dist", v)} />
              </ParamGroup>
              <ParamGroup title="Anchor Filter">
                <ParamSlider label="Endpoint Dist" value={pipe.presetParams.anchor_endpoint_dist ?? 12} min={0} max={30} step={0.5} onChange={(v) => pipe.setPresetParam("anchor_endpoint_dist", v)} />
                <ParamSlider label="Link Dist" value={pipe.presetParams.anchor_link_dist ?? 8} min={0} max={20} step={0.5} onChange={(v) => pipe.setPresetParam("anchor_link_dist", v)} />
              </ParamGroup>
              <button className="reset-btn" onClick={() => { const p = pipe.presets[pipe.preset]; if (p?.params) pipe.setPresetParam("sauvola_k", p.params.sauvola_k); }}>
                Reset to Defaults
              </button>
            </>
          ) : (
            <>
              <div className="legacy-mode-toggle">
                {(["otsu", "manual", "adaptive"] as const).map((mode, i) => (
                  <button key={mode} onClick={() => pipe.setParam("thresh_mode", mode)} className={`dataset-btn ${pipe.params.thresh_mode === mode ? "dataset-btn-active" : ""}`} style={{ borderLeft: i > 0 ? "none" : undefined }}>
                    {mode}
                  </button>
                ))}
              </div>
              {pipe.params.thresh_mode === "manual" && <ParamSlider label="Threshold" value={pipe.params.thresh_val} min={0} max={255} step={1} onChange={(v) => pipe.setParam("thresh_val", v)} />}
              <ParamSlider label="Dilate Kernel" value={pipe.params.dil_ksize} min={1} max={15} step={2} onChange={(v) => pipe.setParam("dil_ksize", v)} />
              <ParamSlider label="Dilate Iters" value={pipe.params.dil_iters} min={0} max={5} step={1} onChange={(v) => pipe.setParam("dil_iters", v)} />
              <ParamSlider label="Min Area" value={pipe.params.min_area} min={0} max={200} step={5} onChange={(v) => pipe.setParam("min_area", v)} />
              <ParamSlider label="Dedup Angle" value={pipe.params.dedup_angle} min={0} max={45} step={1} unit="°" onChange={(v) => pipe.setParam("dedup_angle", v)} />
              <ParamSlider label="Dedup Dist" value={pipe.params.dedup_dist} min={0} max={50} step={1} unit="px" onChange={(v) => pipe.setParam("dedup_dist", v)} />
              <ParamSlider label="Min Length" value={pipe.params.min_line_length} min={0} max={500} step={5} onChange={(v) => pipe.setParam("min_line_length", v)} />
            </>
          )}
        </SidebarSection>

        {pipe.result?.params && (
          <SidebarSection label="Active Config">
            <div className="active-params">
              {Object.entries(pipe.result.params).map(([k, v]) => (
                <span key={k}>{k}: <strong>{String(v)}</strong></span>
              ))}
            </div>
          </SidebarSection>
        )}
      </aside>

      {/* ═══ STATUS BAR ═══ */}
      <div className="status-bar">
        <span className="status-live">● LIVE</span>
        <span>{imgs.imageList.length} imgs</span>
        <span>{pipe.preset}</span>
      </div>
    </div>

      {/* ═══ BOTTOM SHEET (mobile controls — outside grid) ═══ */}
      <div className={`bottom-sheet-overlay ${sheetOpen ? "open" : ""}`} onClick={() => setSheetOpen(false)} />
      <div
        ref={sheetRef}
        className={`bottom-sheet ${sheetOpen ? "open" : ""}`}
        onTouchStart={handleSheetTouchStart}
        onTouchMove={handleSheetTouchMove}
        onTouchEnd={handleSheetTouchEnd}
      >
        <div className="sheet-handle" onClick={() => setSheetOpen(!sheetOpen)}>
          <div className="sheet-handle-bar" />
        </div>
        <div className="sheet-content">
          <div className="sheet-section">
            <div className="sheet-label">PRESET</div>
            <select value={pipe.preset} onChange={(e) => pipe.setPreset(e.target.value)} className="preset-select">
              {Object.entries(pipe.presets).map(([key, p]) => (
                <option key={key} value={key}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className="sheet-section">
            <div className="sheet-label">DATASET</div>
            <div className="dataset-toggle">
              {DATASETS.map((d, i) => (
                <button key={d} onClick={() => imgs.setDataset(d)} className={`dataset-btn ${imgs.dataset === d ? "dataset-btn-active" : ""}`} style={{ borderLeft: i > 0 ? "none" : undefined }}>
                  {DATASET_LABELS[d] ?? d}
                </button>
              ))}
            </div>
          </div>

          <div className="sheet-section">
            <div className="sheet-label">IMAGE</div>
            <div className="image-nav">
              <button className="image-nav-btn" onClick={() => imgs.setImageIdx(Math.max(0, imgs.imageIdx - 1))} disabled={imgs.imageIdx === 0} aria-label="Previous image">←</button>
              <span className="image-nav-count">{imgs.imageIdx + 1} / {imgs.imageList.length}</span>
              <button className="image-nav-btn" onClick={() => imgs.setImageIdx(Math.min(imgs.imageList.length - 1, imgs.imageIdx + 1))} disabled={imgs.imageIdx >= imgs.imageList.length - 1} aria-label="Next image">→</button>
            </div>
            <button type="button" className="image-picker-open-btn" onClick={() => imgs.setPickerOpen(true)} disabled={imgs.listLoading || imgs.imageList.length === 0}>
              Browse all {imgs.imageList.length} images
            </button>
          </div>

          {!pipe.isLegacy ? (
            <>
              <ParamGroup title="Thresholding">
                <ParamSlider label="Sauvola k" value={pipe.presetParams.sauvola_k ?? 0.285} min={0.05} max={0.6} step={0.005} onChange={(v) => pipe.setPresetParam("sauvola_k", v)} />
                <ParamSlider label="Window" value={pipe.presetParams.sauvola_window ?? 67} min={3} max={151} step={2} onChange={(v) => pipe.setPresetParam("sauvola_window", v)} />
                <ParamSlider label="Close Kernel" value={pipe.presetParams.close_kernel ?? 3} min={1} max={15} step={2} onChange={(v) => pipe.setPresetParam("close_kernel", v)} />
              </ParamGroup>
              <ParamGroup title="Component Filtering">
                <ParamSlider label="CCL Min Area" value={pipe.presetParams.ccl_min_area ?? 28} min={0} max={100} step={1} onChange={(v) => pipe.setPresetParam("ccl_min_area", v)} />
              </ParamGroup>
              <ParamGroup title="Deduplication">
                <ParamSlider label="Angle" value={pipe.presetParams.dedup_angle ?? 10} min={0} max={45} step={1} unit="°" onChange={(v) => pipe.setPresetParam("dedup_angle", v)} />
                <ParamSlider label="Distance" value={pipe.presetParams.dedup_dist ?? 18} min={0} max={50} step={1} unit="px" onChange={(v) => pipe.setPresetParam("dedup_dist", v)} />
              </ParamGroup>
              <ParamGroup title="Anchor Filter">
                <ParamSlider label="Endpoint Dist" value={pipe.presetParams.anchor_endpoint_dist ?? 12} min={0} max={30} step={0.5} onChange={(v) => pipe.setPresetParam("anchor_endpoint_dist", v)} />
                <ParamSlider label="Link Dist" value={pipe.presetParams.anchor_link_dist ?? 8} min={0} max={20} step={0.5} onChange={(v) => pipe.setPresetParam("anchor_link_dist", v)} />
              </ParamGroup>
              <button className="reset-btn" onClick={() => { const p = pipe.presets[pipe.preset]; if (p?.params) pipe.setPresetParam("sauvola_k", p.params.sauvola_k); }}>
                Reset to Defaults
              </button>
            </>
          ) : (
            <>
              <div className="legacy-mode-toggle">
                {(["otsu", "manual", "adaptive"] as const).map((mode, i) => (
                  <button key={mode} onClick={() => pipe.setParam("thresh_mode", mode)} className={`dataset-btn ${pipe.params.thresh_mode === mode ? "dataset-btn-active" : ""}`} style={{ borderLeft: i > 0 ? "none" : undefined }}>
                    {mode}
                  </button>
                ))}
              </div>
              {pipe.params.thresh_mode === "manual" && <ParamSlider label="Threshold" value={pipe.params.thresh_val} min={0} max={255} step={1} onChange={(v) => pipe.setParam("thresh_val", v)} />}
              <ParamSlider label="Dilate Kernel" value={pipe.params.dil_ksize} min={1} max={15} step={2} onChange={(v) => pipe.setParam("dil_ksize", v)} />
              <ParamSlider label="Dilate Iters" value={pipe.params.dil_iters} min={0} max={5} step={1} onChange={(v) => pipe.setParam("dil_iters", v)} />
              <ParamSlider label="Min Area" value={pipe.params.min_area} min={0} max={200} step={5} onChange={(v) => pipe.setParam("min_area", v)} />
              <ParamSlider label="Dedup Angle" value={pipe.params.dedup_angle} min={0} max={45} step={1} unit="°" onChange={(v) => pipe.setParam("dedup_angle", v)} />
              <ParamSlider label="Dedup Dist" value={pipe.params.dedup_dist} min={0} max={50} step={1} unit="px" onChange={(v) => pipe.setParam("dedup_dist", v)} />
              <ParamSlider label="Min Length" value={pipe.params.min_line_length} min={0} max={500} step={5} onChange={(v) => pipe.setParam("min_line_length", v)} />
            </>
          )}
        </div>
      </div>

      {/* ═══ IMAGE PICKER MODAL ═══ */}
      {imgs.pickerOpen && (
        <div className="modal-overlay" onClick={() => imgs.setPickerOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">{imgs.imageList.length} images in &quot;{imgs.dataset}&quot;</span>
              <button className="modal-close" onClick={() => imgs.setPickerOpen(false)}>Close</button>
            </div>
            <div className="modal-body">
              <div className="picker-grid">
                {imgs.imageList.map((name, i) => (
                  <button
                    key={name}
                    className={`picker-item ${i === imgs.imageIdx ? "picker-item-active" : ""}`}
                    onClick={() => { imgs.setImageIdx(i); imgs.setPickerOpen(false); }}
                  >
                    <img src={`/api/thumb?idx=${i}&ds=${imgs.dataset}`} alt="" loading="lazy" />
                  </button>
                ))}
              </div>
              {imgs.imageList.length === 0 && !imgs.listLoading && (
                <div className="picker-empty">No images found.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ PREVIEW MODAL ═══ */}
      {preview && (
        <div className="modal-overlay" onClick={() => setPreview(null)}>
          <div className="modal modal-fullscreen" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">{preview.title}</span>
              <button className="modal-close" onClick={() => setPreview(null)}>Close</button>
            </div>
            <div className="modal-preview-body">
              <img src={preview.image} alt={preview.title} className="modal-preview-image" />
            </div>
          </div>
        </div>
      )}

    </>
  );
}
