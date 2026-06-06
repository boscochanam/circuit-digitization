"use client";

import { STAGES, STAGE_PANELS, PANEL_NAMES } from "@/lib/panels";
import type { Stage, PanelIndex } from "@/lib/panels";

interface StageTabsProps {
  activePanel: number;
  onSelectPanel: (panel: number) => void;
}

/**
 * Primary navigation: 3 workflow stages (Detect → Netlist → Simulate).
 * Each stage expands to show its sub-tabs below.
 */
export default function StageTabs({ activePanel, onSelectPanel }: StageTabsProps) {
  // Determine which stage is active
  const activeStage: Stage =
    activePanel <= 3 ? "Detect" : activePanel === 4 || activePanel === 7 ? "Netlist" : "Simulate";

  return (
    <div className="stage-tabs-container">
      {/* Stage selector */}
      <div className="stage-bar">
        {STAGES.map((stage) => (
          <button
            key={stage}
            className={`stage-btn ${activeStage === stage ? "active" : ""}`}
            onClick={() => {
              // Select first panel in the stage
              const panels = STAGE_PANELS[stage];
              onSelectPanel(panels[0]);
            }}
          >
            <span className="stage-num">{STAGES.indexOf(stage) + 1}</span>
            <span className="stage-label">{stage}</span>
          </button>
        ))}
      </div>

      {/* Sub-tabs for active stage */}
      <div className="sub-tabs">
        {STAGE_PANELS[activeStage].map((panelIdx) => (
          <button
            key={panelIdx}
            className={`sub-tab ${activePanel === panelIdx ? "active" : ""}`}
            onClick={() => onSelectPanel(panelIdx)}
          >
            {PANEL_NAMES[panelIdx]}
          </button>
        ))}
      </div>

      <style jsx>{`
        .stage-tabs-container {
          display: flex;
          flex-direction: column;
          gap: 0;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .stage-bar {
          display: flex;
          gap: 2px;
          padding: 6px 12px 0;
        }
        .stage-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 16px;
          border: none;
          border-radius: 8px 8px 0 0;
          background: rgba(255, 255, 255, 0.06);
          color: rgba(255, 255, 255, 0.75);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .stage-btn:hover {
          background: rgba(255, 255, 255, 0.12);
          color: #ffffff;
        }
        .stage-btn.active {
          background: rgba(99, 102, 241, 0.25);
          color: #a5b4fc;
        }
        .stage-num {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.15);
          color: rgba(255, 255, 255, 0.9);
          font-size: 11px;
          font-weight: 700;
        }
        .stage-btn.active .stage-num {
          background: rgba(99, 102, 241, 0.4);
          color: #ffffff;
        }
        .stage-label {
          letter-spacing: 0.02em;
        }
        .sub-tabs {
          display: flex;
          gap: 0;
          padding: 0 12px;
        }
        .sub-tab {
          padding: 8px 14px;
          border: none;
          border-bottom: 2px solid transparent;
          background: transparent;
          color: rgba(255, 255, 255, 0.65);
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .sub-tab:hover {
          color: rgba(255, 255, 255, 0.9);
          background: rgba(255, 255, 255, 0.04);
        }
        .sub-tab.active {
          color: #e0e7ff;
          border-bottom-color: #818cf8;
        }
      `}</style>
    </div>
  );
}
