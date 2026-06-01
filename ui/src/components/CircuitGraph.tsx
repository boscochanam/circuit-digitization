"use client";

import { useState, useEffect, useRef } from "react";
import { fetchNetlistAction } from "@/app/actions";
import type { NetlistResult } from "@/lib/types";

interface Props {
  imageIdx: number;
  dataset: string;
  preset: string;
  params?: Record<string, string | number>;
  className?: string;
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  color: string;
  x: number;
  y: number;
}

interface GraphEdge {
  source: string;
  target: string;
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
  "voltage_source": "#f87171",
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
  // Try exact match, then normalize
  const normalized = type.toLowerCase().replace(/_/g, "-").replace(/\s+/g, "-");
  return TYPE_COLORS[normalized] || TYPE_COLORS[type] || "#94a3b8";
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    resistor: "Resistor", "capacitor-unpolarized": "Capacitor",
    "capacitor-polarized": "Capacitor", inductor: "Inductor",
    diode: "Diode", transistor: "Transistor", junction: "Junction",
    terminal: "Terminal", "voltage_source": "VSource",
    transformer: "Transformer", fuse: "Fuse", switch: "Switch",
    gnd: "GND", crystal: "Crystal",
  };
  return map[type] || type;
}

/** Position components by their actual image coordinates, scaled to viewport. */
function layoutFromData(
  elements: GraphNode[],
  width: number,
  height: number,
): Map<string, { x: number; y: number }> {
  const result = new Map<string, { x: number; y: number }>();

  const positioned = elements.filter(el => el.x !== 0 || el.y !== 0);
  const unpositioned = elements.filter(el => el.x === 0 && el.y === 0);

  if (positioned.length === 0) {
    return circleLayout(elements, width, height);
  }

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const el of positioned) {
    minX = Math.min(minX, el.x);
    minY = Math.min(minY, el.y);
    maxX = Math.max(maxX, el.x);
    maxY = Math.max(maxY, el.y);
  }

  const pad = 80;
  const availW = width - 2 * pad;
  const availH = height - 2 * pad;
  const bboxW = maxX - minX || 1;
  const bboxH = maxY - minY || 1;
  const scale = Math.min(availW / bboxW, availH / bboxH) * 0.85;

  const cx = width / 2;
  const cy = height / 2;
  const dataCx = (minX + maxX) / 2;
  const dataCy = (minY + maxY) / 2;

  for (const el of positioned) {
    result.set(el.id, {
      x: cx + (el.x - dataCx) * scale,
      y: cy + (el.y - dataCy) * scale,
    });
  }

  // Place unpositioned (e.g. auto-injected VSRC) in bottom-right
  if (unpositioned.length > 0) {
    const margin = 60;
    const startX = width - margin - unpositioned.length * 50;
    unpositioned.forEach((el, i) => {
      result.set(el.id, {
        x: Math.max(pad, startX + i * 50),
        y: height - margin,
      });
    });
  }

  return result;
}

function circleLayout(elements: GraphNode[], width: number, height: number): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const cx = width / 2, cy = height / 2;
  const radius = Math.min(width, height) * 0.35;
  elements.forEach((el, i) => {
    const angle = (2 * Math.PI * i) / elements.length - Math.PI / 2;
    positions.set(el.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
  });
  return positions;
}

export default function CircuitGraph({ imageIdx, dataset, preset, params = {} }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dim, setDim] = useState({ w: 600, h: 400 });
  const [selected, setSelected] = useState<string | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);

  // Zoom & pan
  const [scale, setScale] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const dragRef = useRef<{ active: boolean; startX: number; startY: number; panX: number; panY: number }>({ active: false, startX: 0, startY: 0, panX: 0, panY: 0 });

  useEffect(() => {
    const resize = () => {
      if (svgRef.current?.parentElement) {
        const rect = svgRef.current.parentElement.getBoundingClientRect();
        setDim({ w: rect.width, h: Math.max(400, rect.height) });
      }
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchNetlistAction(imageIdx, dataset, preset, params)
      .then((data: NetlistResult) => {
        if (!data.components || data.components.length === 0) {
          setNodes([]);
          setEdges([]);
          setLoading(false);
          return;
        }

        // Build graph nodes from components
        const graphNodes: GraphNode[] = data.components.map(c => ({
          id: c.name,
          label: c.name,
          type: c.type,
          color: getColor(c.type),
          x: c.position?.x ?? 0,
          y: c.position?.y ?? 0,
        }));

        // Build edges from shared nodes in the netlist
        const graphEdges: GraphEdge[] = [];
        const compNameToIdx = new Map<string, number>();
        data.components.forEach((c, i) => compNameToIdx.set(c.name, i));

        if (data.nodes && data.nodes.length > 0) {
          // For each netlist node, connect all components whose pins land on it
          const seen = new Set<string>();
          for (const netNode of data.nodes) {
            const compsOnNode = [...new Set(netNode.pins.map(p => p.component))];
            for (let i = 0; i < compsOnNode.length; i++) {
              for (let j = i + 1; j < compsOnNode.length; j++) {
                const key = [compsOnNode[i], compsOnNode[j]].sort().join("|");
                if (!seen.has(key)) {
                  seen.add(key);
                  graphEdges.push({ source: compsOnNode[i], target: compsOnNode[j] });
                }
              }
            }
          }
        }

        setNodes(graphNodes);
        setEdges(graphEdges);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load netlist");
        setLoading(false);
      });
  }, [imageIdx, dataset, preset, params]);

  // Zoom with mouse wheel
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    setScale(s => Math.max(0.2, Math.min(5, s * factor)));
  };

  // Pan with mouse drag
  const handleMouseDown = (e: React.MouseEvent) => {
    dragRef.current.active = true;
    dragRef.current.startX = e.clientX;
    dragRef.current.startY = e.clientY;
    dragRef.current.panX = panX;
    dragRef.current.panY = panY;
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragRef.current.active) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    setPanX(dragRef.current.panX + dx);
    setPanY(dragRef.current.panY + dy);
  };

  const handleMouseUp = () => {
    dragRef.current.active = false;
  };

  const resetZoom = () => { setScale(1); setPanX(0); setPanY(0); };

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

  if (error) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <div className="netlist-warning">{error}</div>
        </div>
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="panel-content">
        <div className="panel-content-inner">
          <span className="viewport-empty">No circuit components to visualize</span>
        </div>
      </div>
    );
  }

  const hasRealPositions = nodes.some(n => n.x !== 0 || n.y !== 0);
  const positions = layoutFromData(nodes, dim.w, dim.h - 20);

  return (
    <div className="panel-content">
      <div className="panel-content-inner" style={{ padding: 0, position: "relative" }}>
        {hasRealPositions && (
          <div style={{
            padding: "4px 12px", fontSize: 10, color: "#71717a",
            borderBottom: "1px solid #27272a", textAlign: "center",
          }}>
            Components positioned by actual image coordinates
          </div>
        )}
        <svg
          ref={svgRef}
          width={dim.w}
          height={dim.h - 20}
          style={{ background: "var(--bg, #09090b)", cursor: dragRef.current.active ? "grabbing" : "grab" }}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Zoom / pan transform */}
          <g transform={`translate(${panX}, ${panY}) scale(${scale})`}
             style={{ transformOrigin: "0 0" }}>
          {/* Edges */}
          {edges.map((e, i) => {
            const a = positions.get(e.source);
            const b = positions.get(e.target);
            if (!a || !b) return null;
            const isHighlighted = selected === e.source || selected === e.target;
            const isHovered = hoveredEdge === `${e.source}|${e.target}`;
            return (
              <line
                key={`e${i}`}
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={isHighlighted || isHovered ? "#60a5fa" : "#27272a"}
                strokeWidth={isHighlighted ? 2.5 : isHovered ? 2 : 1.5}
                strokeOpacity={isHighlighted ? 1 : 0.6}
                onMouseEnter={() => setHoveredEdge(`${e.source}|${e.target}`)}
                onMouseLeave={() => setHoveredEdge(null)}
                style={{ transition: "stroke 0.15s, stroke-width 0.15s" }}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((el) => {
            const pos = positions.get(el.id);
            if (!pos) return null;
            const isSelected = selected === el.id;
            const r = isSelected ? 28 : 22;
            return (
              <g
                key={el.id}
                onClick={() => setSelected(isSelected ? null : el.id)}
                style={{ cursor: "pointer" }}
              >
                {/* Glow when selected */}
                {isSelected && (
                  <circle cx={pos.x} cy={pos.y} r={r + 8} fill="none" stroke={el.color} strokeWidth={2} opacity={0.3}>
                    <animate attributeName="r" values={`${r + 6};${r + 12};${r + 6}`} dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle
                  cx={pos.x} cy={pos.y} r={r}
                  fill={el.color} fillOpacity={isSelected ? 0.9 : 0.6}
                  stroke={el.color} strokeWidth={isSelected ? 2.5 : 1}
                />
                <text
                  x={pos.x} y={pos.y + 4} textAnchor="middle"
                  fill="#fff" fontSize={isSelected ? 13 : 11}
                  fontWeight={isSelected ? "bold" : "normal"} fontFamily="monospace"
                >
                  {el.id}
                </text>
                {/* Net connections on selected */}
                {isSelected && (() => {
                  const connectedNets = edges
                    .filter(e => e.source === el.id || e.target === el.id)
                    .flatMap(e => {
                      const other = e.source === el.id ? e.target : e.source;
                      const otherPos = positions.get(other);
                      return otherPos ? [{ name: other, x: otherPos.x, y: otherPos.y }] : [];
                    });
                  return connectedNets.map((conn, ni) => {
                    const dx = conn.x - pos.x;
                    const dy = conn.y - pos.y;
                    const dist = Math.hypot(dx, dy);
                    const nx = pos.x + (dx / dist) * 40;
                    const ny = pos.y + (dy / dist) * 40;
                    return (
                      <g key={conn.name}>
                        <circle cx={nx} cy={ny} r={3} fill="#fbbf24" />
                        <text x={nx} y={ny + 12} textAnchor="middle" fill="#a1a1aa" fontSize={8} fontFamily="monospace">
                          {conn.name}
                        </text>
                      </g>
                    );
                  });
                })()}
                {/* Type label */}
                <text
                  x={pos.x} y={pos.y + r + 14} textAnchor="middle"
                  fill={isSelected ? "#f4f4f5" : "#71717a"}
                  fontSize={9} fontFamily="sans-serif"
                >
                  {typeLabel(el.type)}
                </text>
              </g>
            );
          })}
          </g>
        </svg>

        {/* Zoom controls */}
        <div style={{
          position: "absolute", bottom: 48, right: 12, display: "flex",
          flexDirection: "column", gap: 2, zIndex: 10,
        }}>
          <button
            onClick={() => setScale(s => Math.min(5, s * 1.2))}
            style={{
              width: 28, height: 28, border: "1px solid #3f3f46", borderRadius: 4,
              background: "#18181b", color: "#a1a1aa", cursor: "pointer",
              fontSize: 16, lineHeight: 1, display: "flex", alignItems: "center", justifyContent: "center",
            }}
            title="Zoom in"
          >+</button>
          <button
            onClick={resetZoom}
            style={{
              width: 28, height: 28, border: "1px solid #3f3f46", borderRadius: 4,
              background: "#18181b", color: "#a1a1aa", cursor: "pointer",
              fontSize: 10, lineHeight: 1, display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "monospace",
            }}
            title="Reset zoom"
          >{Math.round(scale * 100)}%</button>
          <button
            onClick={() => setScale(s => Math.max(0.2, s / 1.2))}
            style={{
              width: 28, height: 28, border: "1px solid #3f3f46", borderRadius: 4,
              background: "#18181b", color: "#a1a1aa", cursor: "pointer",
              fontSize: 16, lineHeight: 1, display: "flex", alignItems: "center", justifyContent: "center",
            }}
            title="Zoom out"
          >−</button>
        </div>

        {/* Legend + Stats */}
        <div style={{
          padding: "8px 12px", display: "flex", gap: 16, flexWrap: "wrap",
          borderTop: "1px solid #27272a", fontSize: 11, color: "#a1a1aa",
        }}>
          {/* Unique colors in use */}
          {[...new Set(nodes.map(n => n.color))].map(color => {
            const example = nodes.find(n => n.color === color);
            return (
              <span key={color} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, display: "inline-block" }} />
                {example ? typeLabel(example.type) : "?"}
              </span>
            );
          })}
          <span style={{ marginLeft: "auto" }}>
            {nodes.length} components · {edges.length} connections
          </span>
        </div>
      </div>
    </div>
  );
}
