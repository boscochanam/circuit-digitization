"use client";

export function MetricsBar({ result, preset }: {
  result: { line_count: number; blob_count: number; elapsed_ms: number } | null;
  preset: string;
}) {
  return (
    <div className="metrics-bar">
      <div className="metric"><span className="metric-value">{result?.line_count ?? "—"}</span><span className="metric-label">Lines</span></div>
      <div className="metric"><span className="metric-value">{result?.blob_count ?? "—"}</span><span className="metric-label">Blobs</span></div>
      <div className="metric"><span className="metric-value">{result?.elapsed_ms?.toFixed(1) ?? "—"}</span><span className="metric-label">ms</span></div>
      <div className="metric-preset">{preset}</div>
    </div>
  );
}

export function PanelTabs({ panels, activePanel, onSelect }: {
  panels: readonly string[];
  activePanel: number;
  onSelect: (i: number) => void;
}) {
  return (
    <div className="panel-tabs">
      {panels.map((name, i) => (
        <button
          key={name}
          className={`panel-tab ${i === activePanel ? "panel-tab-active" : ""}`}
          onClick={() => onSelect(i)}
        >
          {name.split(" ")[0]}
        </button>
      ))}
    </div>
  );
}

export function ImageViewport({ panelImage, panelTitle, loading, listLoading, listError, pipelineError, imageList, imageIdx, onPrev, onNext, onGrid, onTouchStart, onTouchEnd }: {
  panelImage: { base64?: string; src?: string };
  panelTitle: string;
  loading: boolean;
  listLoading: boolean;
  listError: string | null;
  pipelineError: string | null;
  imageList: string[];
  imageIdx: number;
  onPrev: () => void;
  onNext: () => void;
  onGrid: () => void;
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
}) {
  return (
    <main className="image-viewport" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
        </div>
      )}

      {panelImage.base64 ? (
        <img src={`data:image/jpeg;base64,${panelImage.base64}`} alt={panelTitle} className="viewport-image" />
      ) : panelImage.src ? (
        <img src={panelImage.src} alt={panelTitle} className="viewport-image" />
      ) : (
        <div className="viewport-empty">
          {listLoading
            ? "Loading images…"
            : listError
              ?? (pipelineError && imageList.length > 0 ? pipelineError : null)
              ?? (imageList.length === 0
                ? "No images — is wire-tune running on :8000?"
                : loading
                  ? "Running pipeline…"
                  : "No data")}
        </div>
      )}

      <div className="panel-label">{panelTitle}</div>

      <button
        className="nav-arrow nav-arrow-left"
        onClick={(e) => { e.stopPropagation(); onPrev(); }}
        disabled={imageIdx === 0}
        aria-label="Previous image"
      >
        ‹
      </button>
      <button
        className="nav-arrow nav-arrow-right"
        onClick={(e) => { e.stopPropagation(); onNext(); }}
        disabled={imageIdx >= imageList.length - 1}
        aria-label="Next image"
      >
        ›
      </button>

      <span className="nav-counter">{imageIdx + 1}/{imageList.length}</span>
      <button className="nav-grid-toggle" onClick={onGrid} aria-label="Switch to grid view">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="1" y="1" width="5" height="5" fill="currentColor"/>
          <rect x="10" y="1" width="5" height="5" fill="currentColor"/>
          <rect x="1" y="10" width="5" height="5" fill="currentColor"/>
          <rect x="10" y="10" width="5" height="5" fill="currentColor"/>
        </svg>
      </button>
    </main>
  );
}

export function ImageGrid({ imageList, imageIdx, dataset, gridCount, gridScrollRef, onScroll, onSelect }: {
  imageList: string[];
  imageIdx: number;
  dataset: string;
  gridCount: number;
  gridScrollRef: React.RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  onSelect: (i: number) => void;
}) {
  return (
    <main className="grid-viewport">
      <div className="grid-header">
        <span className="grid-header-title">{imageList.length} images</span>
      </div>
      <div className="grid-scroll" ref={gridScrollRef} onScroll={onScroll}>
        {imageList.slice(0, gridCount).map((name, i) => (
          <button
            key={name}
            className={`grid-thumb ${i === imageIdx ? "grid-thumb-active" : ""}`}
            onClick={() => onSelect(i)}
          >
            <img src={`/api/thumb?idx=${i}&ds=${dataset}`} alt="" loading="lazy" />
            <span className="grid-thumb-idx">{i + 1}</span>
          </button>
        ))}
        {gridCount < imageList.length && (
          <div className="grid-loading">
            <div className="loading-spinner" />
            <span>Loading {gridCount}/{imageList.length}</span>
          </div>
        )}
      </div>
    </main>
  );
}

export function SidebarSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="sidebar-section">
      <div className="sidebar-section-label">{label}</div>
      {children}
    </div>
  );
}

export function ParamGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="param-group">
      <div className="param-group-title">{title}</div>
      {children}
    </div>
  );
}

export function ParamSlider({ label, value, min, max, step, unit, onChange }: {
  label: string; value: number; min: number; max: number; step: number; unit?: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="param-slider">
      <span className="param-slider-label">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="param-slider-input"
      />
      <span className="param-slider-value">{value}{unit ?? ""}</span>
    </div>
  );
}

export function ToolbarStat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="toolbar-stat">
      <span className="toolbar-stat-value">{value}</span>
      <span className="toolbar-stat-label">{label}</span>
    </div>
  );
}

export function ImagePanel({ title, base64, src, loading, error, onClick }: {
  title: string; base64?: string; src?: string; loading?: boolean; error?: string | null;
  onClick?: () => void;
}) {
  return (
    <div className="desktop-panel" onClick={onClick}>
      <div className="desktop-panel-title">{title}</div>
      <div className="desktop-panel-body">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner" />
          </div>
        )}
        {base64 ? (
          <img src={`data:image/jpeg;base64,${base64}`} alt={title} className="desktop-panel-image" />
        ) : src ? (
          <img src={src} alt={title} className="desktop-panel-image" />
        ) : (
          <span className="viewport-empty">{loading ? "Running…" : error ?? "No data"}</span>
        )}
      </div>
    </div>
  );
}
