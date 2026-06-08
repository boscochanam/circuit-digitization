"use client";

import type { BottomPanelTab } from "@/lib/types";

interface BottomPanelProps {
  activeTab: BottomPanelTab;
  onTabChange: (tab: string) => void;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

const TABS: { value: BottomPanelTab; label: string }[] = [
  { value: "netlist", label: "Netlist" },
  { value: "warnings", label: "Warnings" },
  { value: "raw", label: "Raw" },
  { value: "graph", label: "Graph" },
];

export default function BottomPanel({
  activeTab,
  onTabChange,
  isOpen,
  onToggle,
  children,
}: BottomPanelProps) {
  return (
    <div className={`bottom-panel ${isOpen ? "bottom-panel-open" : ""}`}>
      <div className="bottom-panel-header">
        <div className="bottom-panel-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              className={`bottom-panel-tab ${activeTab === tab.value ? "bottom-panel-tab-active" : ""}`}
              onClick={() => onTabChange(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button
          className="bottom-panel-close"
          onClick={onToggle}
          aria-label="Toggle panel"
        >
          {isOpen ? "−" : "+"}
        </button>
      </div>

      <div className="bottom-panel-content">
        {children}
      </div>
    </div>
  );
}
