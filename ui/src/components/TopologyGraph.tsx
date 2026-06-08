"use client";

import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useState } from "react";
import type { TopologyResult, TopoComponent } from "@/lib/types";

/* ── Props ── */
interface TopologyGraphProps {
  topology: TopologyResult;
  selectedNode: number | null;
  selectedComponent: string | null;
  onNodeSelect: (nodeId: number | null) => void;
  onComponentSelect: (name: string | null) => void;
}

/* ── Color map by component type ── */
const TYPE_COLORS: Record<string, string> = {
  resistor: "#22c55e",
  capacitor: "#3b82f6",
  inductor: "#06b6d4",
  "voltage-DC": "#ef4444",
  "voltage-AC": "#ef4444",
  diode: "#eab308",
  transistor: "#a855f7",
  mosfet: "#a855f7",
  bjt: "#a855f7",
  opamp: "#f97316",
  junction: "#888888",
  terminal: "#888888",
  connector: "#888888",
};
const DEFAULT_COLOR = "#94a3b8";

function typeColor(type: string): string {
  if (TYPE_COLORS[type]) return TYPE_COLORS[type];
  const t = type.toLowerCase();
  if (t.startsWith("r")) return TYPE_COLORS.resistor;
  if (t.startsWith("c")) return TYPE_COLORS.capacitor;
  if (t.startsWith("l")) return TYPE_COLORS.inductor;
  if (t.startsWith("v")) return TYPE_COLORS["voltage-DC"];
  if (t.startsWith("d")) return TYPE_COLORS.diode;
  if (t.startsWith("q")) return TYPE_COLORS.bjt;
  if (t.startsWith("j")) return TYPE_COLORS.connector;
  return DEFAULT_COLOR;
}

/* ── Custom node component ── */
function CircuitNode({
  data,
  selected,
}: NodeProps) {
  const d = data as unknown as {
    label: string;
    type: string;
    color: string;
    dimmed: boolean;
  };
  const size = 44;
  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <div
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          background: d.color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: selected
            ? "2.5px solid #fff"
            : "1.5px solid rgba(255,255,255,0.25)",
          boxShadow: selected
            ? `0 0 12px 4px ${d.color}88`
            : "0 1px 3px rgba(0,0,0,0.3)",
          opacity: d.dimmed ? 0.3 : 1,
          transition: "opacity 0.2s, box-shadow 0.2s",
          cursor: "pointer",
        }}
      >
        <span
          style={{
            color: "#fff",
            fontSize: 9,
            fontWeight: 700,
            lineHeight: 1,
            textAlign: "center",
            userSelect: "none",
          }}
        >
          {d.label}
        </span>
      </div>
      {selected && (
        <div
          style={{
            position: "absolute",
            top: size + 2,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: 8,
            color: d.color,
            whiteSpace: "nowrap",
            fontWeight: 600,
          }}
        >
          {d.type}
        </div>
      )}
    </>
  );
}

const nodeTypes = { circuit: CircuitNode };

/* ── Main component ── */
export default function TopologyGraph({
  topology,
  selectedComponent,
  onComponentSelect,
}: TopologyGraphProps) {
  /* Build React Flow nodes from topology components */
  const initialNodes: Node[] = useMemo(() => {
    const { components } = topology;
    if (!components.length) return [];

    // Compute bounding box of all components to scale positions into 0-800 space
    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;
    for (const c of components) {
      const [x1, y1, x2, y2] = c.bbox;
      if (x1 < minX) minX = x1;
      if (y1 < minY) minY = y1;
      if (x2 > maxX) maxX = x2;
      if (y2 > maxY) maxY = y2;
    }

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const scale = 800 / Math.max(rangeX, rangeY);
    const offsetX = (800 - rangeX * scale) / 2;
    const offsetY = (600 - rangeY * scale) / 2;

    return components.map((c: TopoComponent) => {
      const [x1, y1, x2, y2] = c.bbox;
      const cx = ((x1 + x2) / 2 - minX) * scale + offsetX;
      const cy = ((y1 + y2) / 2 - minY) * scale + offsetY;
      return {
        id: `comp-${c.idx}`,
        type: "circuit",
        position: { x: cx - 22, y: cy - 22 },
        data: {
          label: c.name,
          type: c.type,
          color: typeColor(c.type),
          dimmed: false,
          componentIdx: c.idx,
        },
      };
    });
  }, [topology]);

  /* Build edges: connect all components sharing a netlist node */
  const initialEdges: Edge[] = useMemo(() => {
    const { components } = topology;
    if (!components.length) return [];

    // Map netlist node → list of component indices
    const nodeToComps = new Map<number, number[]>();
    for (const c of components) {
      for (const nid of c.node_ids) {
        if (nid === null || nid === undefined) continue;
        if (!nodeToComps.has(nid)) nodeToComps.set(nid, []);
        nodeToComps.get(nid)!.push(c.idx);
      }
    }

    // Deduplicate edges (A→B same as B→A)
    const edgeSet = new Set<string>();
    const edges: Edge[] = [];
    for (const [nodeId, compIds] of nodeToComps) {
      for (let i = 0; i < compIds.length; i++) {
        for (let j = i + 1; j < compIds.length; j++) {
          const a = compIds[i];
          const b = compIds[j];
          const key = a < b ? `${a}-${b}` : `${b}-${a}`;
          if (edgeSet.has(key)) continue;
          edgeSet.add(key);
          edges.push({
            id: `edge-comp${a}-comp${b}-n${nodeId}`,
            source: `comp-${a}`,
            target: `comp-${b}`,
            type: "straight",
            label: `N${nodeId}`,
            style: {
              stroke: "#64748b",
              strokeWidth: 1.5,
            },
            labelStyle: {
              fontSize: 8,
              fill: "#94a3b8",
            },
          });
        }
      }
    }
    return edges;
  }, [topology]);

  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);

  // Update dimming when selection changes
  const displayNodes = useMemo(() => {
    if (!selectedComponent) {
      return nodes.map((n) => ({
        ...n,
        data: { ...(n.data as object), dimmed: false },
      }));
    }
    // Find the selected component's node_ids
    const selComp = topology.components.find(
      (c) => c.name === selectedComponent,
    );
    const connectedNodeIds = new Set(selComp?.node_ids ?? []);
    // Find all component idxs connected to the same netlist nodes
    const connectedCompIdxs = new Set<number>();
    if (selComp) connectedCompIdxs.add(selComp.idx);
    for (const c of topology.components) {
      for (const nid of c.node_ids) {
        if (connectedNodeIds.has(nid)) connectedCompIdxs.add(c.idx);
      }
    }
    return nodes.map((n) => ({
      ...n,
      data: {
        ...(n.data as object),
        dimmed: !connectedCompIdxs.has(
          (n.data as unknown as { componentIdx: number }).componentIdx,
        ),
      },
    }));
  }, [nodes, selectedComponent, topology]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds));
    },
    [setNodes],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      setEdges((eds) => applyEdgeChanges(changes, eds));
    },
    [setEdges],
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const d = node.data as unknown as { label: string };
      onComponentSelect(d.label);
    },
    [onComponentSelect],
  );

  const onPaneClick = useCallback(() => {
    onComponentSelect(null);
  }, [onComponentSelect]);

  if (!topology.components.length) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "#64748b",
          fontSize: 13,
        }}
      >
        No components to display
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={displayNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        style={{ background: "#0f172a" }}
      >
        <Background color="#1e293b" gap={20} />
        <Controls
          style={{ background: "#1e293b", borderColor: "#334155" }}
        />
      </ReactFlow>
    </div>
  );
}
