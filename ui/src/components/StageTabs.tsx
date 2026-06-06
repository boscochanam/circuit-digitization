"use client";

import { STAGES, STAGE_PANELS, PANEL_NAMES } from "@/lib/panels";
import type { Stage } from "@/lib/panels";

interface StageTabsProps {
  activePanel: number;
  onSelectPanel: (panel: number) => void;
}

/**
 * Primary navigation: 3 workflow stages (Detect → Netlist → Simulate).
 * Each stage expands to show its sub-tabs below.
 * Matches existing design system: white bg, black active, uppercase labels.
 */
export default function StageTabs({ activePanel, onSelectPanel }: StageTabsProps) {
  const activeStage: Stage =
    activePanel <= 3 ? "Detect" : activePanel === 4 || activePanel === 7 ? "Netlist" : "Simulate";

  return (
    <div className="stage-tabs-wrap">
      {/* Stage selector */}
      <div className="stage-bar">
        {STAGES.map((stage, i) => (
          <button
            key={stage}
            className={`stage-btn ${activeStage === stage ? "stage-btn-active" : ""}`}
            onClick={() => onSelectPanel(STAGE_PANELS[stage][0])}
          >
            {i + 1}. {stage}
          </button>
        ))}
      </div>

      {/* Sub-tabs for active stage */}
      <div className="sub-tabs">
        {STAGE_PANELS[activeStage].map((panelIdx) => (
          <button
            key={panelIdx}
            className={`sub-tab ${activePanel === panelIdx ? "sub-tab-active" : ""}`}
            onClick={() => onSelectPanel(panelIdx)}
          >
            {PANEL_NAMES[panelIdx]}
          </button>
        ))}
      </div>

      <style jsx>{`
        .stage-tabs-wrap {
          border-top: 2px solid var(--black);
          border-bottom: 3px solid var(--black);
          background: var(--white);
        }
        .stage-bar {
          display: flex;
          gap: 0;
          background: var(--grey-light);
          border-bottom: 1px solid var(--black);
        }
        .stage-btn {
          flex: 1;
          font-family: var(--font-body), sans-serif;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 8px 12px;
          background: var(--grey-light);
          color: var(--grey-dark);
          border: none;
          border-right: 1px solid rgba(0, 0, 0, 0.15);
          cursor: pointer;
          transition: background 0.1s, color 0.1s;
        }
        .stage-btn:last-child { border-right: none; }
        .stage-btn:hover { background: var(--white); }
        .stage-btn-active {
          background: var(--black);
          color: var(--white);
        }
        .sub-tabs {
          display: flex;
          gap: 0;
        }
        .sub-tab {
          flex: 1;
          font-family: var(--font-body), sans-serif;
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 10px 8px;
          background: var(--white);
          color: var(--grey-dark);
          border: none;
          border-right: 1px solid var(--black);
          cursor: pointer;
          transition: background 0.1s, color 0.1s;
        }
        .sub-tab:last-child { border-right: none; }
        .sub-tab:hover { background: var(--grey-light); }
        .sub-tab-active {
          background: var(--black);
          color: var(--white);
        }
      `}</style>
    </div>
  );
}
