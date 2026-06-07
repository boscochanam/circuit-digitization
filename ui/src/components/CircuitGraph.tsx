"use client";

import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  ReactFlowProvider,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
  type FitViewOptions,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useNetlist } from "@/hooks/useNetlist";
import type { NetlistResult } from "@/lib/types";
import CircuitNode from "./CircuitNode";

interface Props {
  imageIdx: number;
  dataset: string;
  preset: string;
  params?: Record<string, string | number>;
  className?: string;
  componentValues?: Record<string, string>;
  onValueChange?: (name: string, value: string) => void;
  selectedComponent?: string | null;
  onComponentSelect?: (name: string | null) => void;
  nodeVoltages?: Array<{ node: string; voltage: number }>;
  showVoltage?: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  resistor: "#4ade80", "resistor-adjustable": "#4ade80",
  thermistor: "#4ade80", varistor: "#4ade80",
  "capacitor-unpolarized": "#60a5fa", "capacitor-polarized": "#60a5fa",
  "capacitor-adjustable": "#60a5fa",
  inductor: "#f472b6", "inductor-ferrite": "#f472b6",
  transformer: "#f472b6",
  diode: "#fb923c", "diode-zener": "#fb923c", "diode-light_emitting": "#fb923c",
  "diode-thyrector": "#fb923c", diac: "#fb923c",
  transistor: "#a78bfa", "transistor-pnp": "#a78bfa",
  voltage_source: "#f87171",
  junction: "#2dd4bf",
  terminal: "#e879f9",
  gnd: "#f87171",
  fuse: "#f97316",
  lamp: "#f472b6",
  switch: "#facc15",
  relay: "#facc15",
  crystal: "#fbbf24",
  motor: "#fbbf24",
  microphone: "#fbbf24",
  probe: "#fbbf24",
  integrated_circuit: "#fbbf24",
  "integrated_circuit-ne555": "#fbbf24",
  "integrated_circuit-voltage_regulator": "#fbbf24",
  operational_amplifier: "#fbbf24",
  and: "#fbbf24", nand: "#fbbf24", or: "#fbbf24", not: "#fbbf24",
  potentiometer: "#c084fc",
  optocoupler: "#c084fc",
  triac: "#a78bfa",
  antenna: "#94a3b8",
};

function getColor(type: string): string {
  const normalized = type.toLowerCase().replace(/_/g, "-").replace(/\s+/g, "-");
  return TYPE_COLORS[normalized] || TYPE_COLORS[type] || "#94a3b8";
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    resistor: "Resistor", "capacitor-unpolarized": "Capacitor",
    "capacitor-polarized": "Capacitor", inductor: "Inductor",
    diode: "Diode", transistor: "Transistor", junction: "Junction",
    terminal: "Terminal", voltage_source: "VSource",
    transformer: "Transformer", fuse: "Fuse", switch: "Switch",
    gnd: "GND", crystal: "Crystal",
  };
  return map[type] || type;
}

/** Normalize image coords to a sensible coordinate space (0–800) */
function computeLayout(
  components: Array<{ name: string; position?: { x: number; y: number } }>,
): Map<string, { x: number; y: number }> {
  const layout = new Map<string, { x: number; y: number }>();
  const SPACE = 800;
  const positioned = components.filter((c) => c.position);
  const unpositioned = components.filter((c) => !c.position);
  if (positioned.length === 0) return layout;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const c of positioned) {
    minX = Math.min(minX, c.position!.x);
    minY = Math.min(minY, c.position!.y);
    maxX = Math.max(maxX, c.position!.x);
    maxY = Math.max(maxY, c.position!.y);
  }
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const pad = 60;
  const avail = SPACE - 2 * pad;
  for (const c of positioned) {
    const nx = (c.position!.x - minX) / rangeX;
    const ny = (c.position!.y - minY) / rangeY;
    layout.set(c.name, { x: pad + nx * avail, y: pad + ny * avail });
  }

  if (unpositioned.length > 0) {
    const margin = 60;
    unpositioned.forEach((c, i) => {
      layout.set(c.name, {
        x: SPACE - margin - (unpositioned.length - 1 - i) * 50,
        y: SPACE - margin,
      });
    });
  }
  return layout;
}

const fitViewOpts: FitViewOptions = { padding: 0.25, duration: 200 };
const nodeTypes = { circuitNode: CircuitNode } as any;

function InnerCircuitGraph({
  imageIdx,
  dataset,
  preset,
  params = {},
  componentValues = {},
  onValueChange,
  selectedComponent: externalSelected,
  onComponentSelect,
  nodeVoltages,
  showVoltage,
}: Props) {
  const rfWrapper = useRef<HTMLDivElement>(null);
  const [rfInstance, setRfInstance] = useState<any>(null);
  const [componentScale, setComponentScale] = useState(1.0);

  // Managed node/edge change handlers
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null);
  const { netlist, loading, error } = useNetlist(imageIdx, dataset, preset, params as Record<string, number>);

  // Use external selection if provided, otherwise fall back to internal
  const selectedId = externalSelected !== undefined ? externalSelected : internalSelectedId;

  // Managed node/edge change handlers
  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  // Process netlist into React Flow nodes/edges
  useEffect(() => {
    if (!netlist || !netlist.components || netlist.components.length === 0) {
      setNodes([]);
      setEdges([]);
      if (onComponentSelect) {
        onComponentSelect(null);
      } else {
        setInternalSelectedId(null);
      }
      return;
    }

    const layout = computeLayout(netlist.components);

    const rfNodes: Node[] = netlist.components.map((c) => {
      const pos = layout.get(c.name) || { x: 400, y: 400 };
      return {
        id: c.name,
        type: "circuitNode",
        position: { x: pos.x, y: pos.y },
        width: 40,
        height: 40,
        data: {
          label: c.name,
          typeLabel: typeLabel(c.type),
          color: getColor(c.type),
          value: componentValues[c.name] ?? "",
          onValueChange: onValueChange ?? undefined,
        },
      };
    });

    const rfEdges: Edge[] = [];
    const seen = new Set<string>();
    if (netlist.nodes) {
      for (const netNode of netlist.nodes) {
        const compsOnNode = [...new Set(netNode.pins.map((p: any) => p.component))];
        for (let i = 0; i < compsOnNode.length; i++) {
          for (let j = i + 1; j < compsOnNode.length; j++) {
            const key = [compsOnNode[i], compsOnNode[j]].sort().join("|");
            if (!seen.has(key)) {
              seen.add(key);
              rfEdges.push({
                id: key,
                source: compsOnNode[i],
                target: compsOnNode[j],
                type: "straight",
                style: { stroke: "#27272a", strokeWidth: 1.5, opacity: 0.6 },
              });
            }
          }
        }
      }
    }

    setNodes(rfNodes);
    setEdges(rfEdges);
    if (onComponentSelect) {
      onComponentSelect(null);
    } else {
      setInternalSelectedId(null);
    }
  }, [netlist]);

  // Fit view on first load and when scale resets near 1.0
  const hasFitRef = useRef(false);
  useEffect(() => {
    if (rfInstance && nodes.length > 0) {
      requestAnimationFrame(() => {
        rfInstance.fitView(fitViewOpts);
      });
    }
  }, [rfInstance, nodes.length, componentScale]);

  const onInit = useCallback((instance: any) => {
    setRfInstance(instance);
  }, []);

  // Handle node click — toggle selection
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const next = selectedId === node.id ? null : node.id;
    if (onComponentSelect) {
      onComponentSelect(next);
    } else {
      setInternalSelectedId(next);
    }
  }, [selectedId, onComponentSelect]);

  // Click on background to deselect
  const onPaneClick = useCallback(() => {
    if (onComponentSelect) {
      onComponentSelect(null);
    } else {
      setInternalSelectedId(null);
    }
  }, [onComponentSelect]);

  // Highlight connected edges & connected nodes on selection
  const nodeHighlight = useMemo(() => {
    const edgeIds = new Set<string>();
    const nodeIds = new Set<string>();
    if (!selectedId) return { edgeIds, nodeIds };
    nodeIds.add(selectedId);
    for (const edge of edges) {
      if (edge.source === selectedId || edge.target === selectedId) {
        edgeIds.add(edge.id);
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
      }
    }
    return { edgeIds, nodeIds };
  }, [selectedId, edges]);

  // Apply highlight styles to edges
  const styledEdges = useMemo(() =>
    edges.map((e) => {
      if (!selectedId) {
        return { ...e, style: { stroke: "#52525b", strokeWidth: 2, opacity: 0.85 } };
      }
      const isHighlighted = nodeHighlight.edgeIds.has(e.id);
      return {
        ...e,
        style: isHighlighted
          ? { stroke: "#60a5fa", strokeWidth: 3, opacity: 1 }
          : { stroke: "#3f3f46", strokeWidth: 1, opacity: 0.2 },
      };
    }),
    [edges, selectedId, nodeHighlight],
  );

  // Apply scale to nodes
  const scaledNodes = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        width: 40 * componentScale,
        height: 40 * componentScale,
        data: { ...n.data, scale: componentScale },
      })),
    [nodes, componentScale],
  );

  // Apply dimming to nodes (after scaling)
  const styledNodes = useMemo(
    () =>
      scaledNodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          dimmed: selectedId !== null && !nodeHighlight.nodeIds.has(n.id),
          voltage: showVoltage && nodeVoltages
            ? nodeVoltages.find((v) => v.node === n.id)?.voltage
            : undefined,
          showVoltage,
        },
      })),
    [scaledNodes, selectedId, nodeHighlight, nodeVoltages, showVoltage],
  );

  // Loading state
  if (loading) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <div className="loading-overlay"><div className="loading-spinner" /></div>
          <span className="viewport-empty">Loading circuit topology…</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <div className="netlist-warning">{error}</div>
        </div>
      </div>
    );
  }

  // Empty state
  if (nodes.length === 0) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <span className="viewport-empty">No circuit components to visualize</span>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-content">
      <div className="panel-content-inner" style={{ padding: 0, position: "relative" }}>
        <div style={{
          padding: "4px 12px", fontSize: 10, color: "#71717a",
          borderBottom: "1px solid #27272a", textAlign: "center",
        }}>
          Components positioned by actual image coordinates
        </div>

        <div ref={rfWrapper} style={{ width: "100%", height: 400 }}>
          <ReactFlow
            nodes={styledNodes}
            edges={styledEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={onInit}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView={false}
            minZoom={0.1}
            maxZoom={4}
            panOnDrag={true}
            selectionOnDrag={false}
            selectNodesOnDrag={false}
            nodeOrigin={[0.5, 0.5]}
            style={{ background: "#09090b" }}
            colorMode="dark"
          >
            <Background color="#18181b" gap={20} size={1} />
            <Controls showInteractive={false} position="bottom-right" />
          </ReactFlow>
        </div>

        {/* Scale slider */}
        <div style={{
          padding: "4px 12px", display: "flex", alignItems: "center", gap: 8,
          borderTop: "1px solid #27272a", fontSize: 11, color: "#a1a1aa",
        }}>
          <span>Scale</span>
          <input
            type="range"
            min={0.3}
            max={3.0}
            step={0.1}
            value={componentScale}
            onChange={(e) => setComponentScale(parseFloat(e.target.value))}
            style={{
              flex: 1, maxWidth: 160, height: 4, accentColor: "#60a5fa",
              cursor: "pointer", background: "#27272a", borderRadius: 2,
            }}
          />
          <span style={{ fontFamily: "monospace", width: 32, textAlign: "right" }}>
            {componentScale.toFixed(1)}×
          </span>
        </div>

        {/* Legend + Stats */}
        <div style={{
          padding: "8px 12px", display: "flex", gap: 16, flexWrap: "wrap",
          borderTop: "1px solid #27272a", fontSize: 11, color: "#a1a1aa",
        }}>
          {[...new Set(nodes.map((n) => n.data.color as string))].map((color) => {
            const example = nodes.find((n) => n.data.color === color);
            return (
              <span key={color} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, display: "inline-block" }} />
                {example ? typeLabel(example.data.typeLabel as string) : "?"}
              </span>
            );
          })}
          <span style={{ marginLeft: "auto" }}>
            {nodes.length} components · {edges.length} connections
            {selectedId && ` · selected: ${selectedId}`}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function CircuitGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <InnerCircuitGraph {...props} />
    </ReactFlowProvider>
  );
}
