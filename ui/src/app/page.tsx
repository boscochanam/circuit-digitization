"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";

import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { listImages, runPipeline } from "@/lib/api";

const DATASETS = ["hand_drawn", "synthetic", "database"] as const;
type Dataset = (typeof DATASETS)[number];

export default function Home() {
  const [dataset, setDataset] = useState<Dataset>("hand_drawn");
  const [imageIdx, setImageIdx] = useState(0);
  const [imageList, setImageList] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    line_count: number; blob_count: number; elapsed_ms: number;
    overlay: string; threshold: string; dilated: string;
  } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [params, setParams] = useState({
    thresh_mode: "otsu" as "otsu" | "manual" | "adaptive",
    thresh_val: 127,
    dil_ksize: 5,
    dil_iters: 1,
    min_area: 30,
    dedup_angle: 10,
    dedup_dist: 12,
    min_line_length: 20,
  });

  useEffect(() => {
    listImages(dataset).then((list) => {
      setImageList(list);
      setImageIdx(0);
    });
  }, [dataset]);

  const doRun = useCallback(
    (idx: number, p: typeof params) => {
      if (abortRef.current) abortRef.current.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      setLoading(true);
      fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ img_idx: idx, ds: dataset, params: p }),
        signal: ctrl.signal,
      })
        .then((r) => r.json())
        .then((data) => {
          if (!ctrl.signal.aborted) {
            setResult(data);
            setLoading(false);
          }
        })
        .catch(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    },
    [dataset],
  );

  useEffect(() => {
    if (imageList.length > 0) doRun(imageIdx, params);
  }, [imageIdx, params, dataset, imageList, doRun]);

  const setParam = (key: string, value: number | string) =>
    setParams((p) => ({ ...p, [key]: value }));

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      {/* ── Sidebar ── */}
      <aside className="w-80 flex flex-col border-r border-zinc-800 bg-zinc-900 p-4 gap-3 overflow-y-auto">
        <h1 className="text-lg font-bold tracking-tight">Wire Detection Tuner</h1>

        <div>
          <label className="text-xs text-zinc-400 mb-1 block">Dataset</label>
          <div className="flex gap-1">
            {DATASETS.map((d) => (
              <Button
                key={d}
                variant={dataset === d ? "default" : "outline"}
                size="sm"
                className="flex-1"
                onClick={() => setDataset(d)}
              >
                {d === "hand_drawn" ? "Hand Drawn" : "Database"}
              </Button>
            ))}
          </div>
        </div>

        <Button variant="outline" size="sm" onClick={() => setPickerOpen(true)} className="h-20 p-1">
          {imageList[imageIdx] ? (
            <img
              src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/thumb?idx=${imageIdx}&ds=${dataset}`}
              alt=""
              className="w-full h-full object-contain rounded"
            />
          ) : (
            "Select Image"
          )}
        </Button>

        <Separator />

        <div className="flex items-center gap-2">
          <Button
            variant={params.thresh_mode === "otsu" ? "default" : "outline"}
            size="sm"
            className="flex-1"
            onClick={() => setParam("thresh_mode", "otsu")}
          >
            Otsu
          </Button>
          <Button
            variant={params.thresh_mode === "manual" ? "default" : "outline"}
            size="sm"
            className="flex-1"
            onClick={() => setParam("thresh_mode", "manual")}
          >
            Manual
          </Button>
        </div>

        {params.thresh_mode === "manual" && (
          <ParamSlider
            label="Threshold Value"
            value={params.thresh_val}
            min={0}
            max={255}
            step={1}
            onChange={(v) => setParam("thresh_val", v)}
          />
        )}

        <ParamSlider label="Dilate Kernel" value={params.dil_ksize} min={1} max={15} step={2} onChange={(v) => setParam("dil_ksize", v)} />
        <ParamSlider label="Dilate Iterations" value={params.dil_iters} min={0} max={5} step={1} onChange={(v) => setParam("dil_iters", v)} />
        <ParamSlider label="Min Area" value={params.min_area} min={0} max={200} step={5} onChange={(v) => setParam("min_area", v)} />
        <ParamSlider label="Dedup Angle" value={params.dedup_angle} min={0} max={45} step={1} onChange={(v) => setParam("dedup_angle", v)} />
        <ParamSlider label="Dedup Distance" value={params.dedup_dist} min={0} max={50} step={1} onChange={(v) => setParam("dedup_dist", v)} />
        <ParamSlider label="Min Line Length" value={params.min_line_length} min={0} max={500} step={5} onChange={(v) => setParam("min_line_length", v)} />

        <Separator />

        {result && (
          <div className="text-xs text-zinc-400 space-y-1">
            <div>Lines: <span className="text-zinc-100 font-mono">{result.line_count}</span></div>
            <div>Blobs: <span className="text-zinc-100 font-mono">{result.blob_count}</span></div>
            <div>Time: <span className="text-zinc-100 font-mono">{result.elapsed_ms.toFixed(1)}ms</span></div>
          </div>
        )}
      </aside>

      {/* ── Image Grid ── */}
      <main className="flex-1 p-4 grid grid-cols-2 grid-rows-2 gap-3">
        <Panel title="Detected Lines" image={result?.overlay} loading={loading} />
        <Panel title="Threshold" image={result?.threshold} loading={loading} />
        <Panel title="Dilated" image={result?.dilated} loading={loading} />
        <Panel title="Source" image={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/thumb?idx=${imageIdx}&ds=${dataset}`} loading={false} isThumb />
      </main>

      {/* ── Image Picker Dialog ── */}
      <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <DialogContent className="max-w-[95vw] max-h-[95vh] w-full h-full bg-zinc-950 border-zinc-800 p-6">
          <div className="grid grid-cols-8 gap-2 overflow-y-auto max-h-[85vh]">
            {imageList.map((name, i) => (
              <button
                key={name}
                className={`border-2 rounded overflow-hidden aspect-square ${i === imageIdx ? "border-blue-500" : "border-transparent hover:border-zinc-500"}`}
                onClick={() => {
                  setImageIdx(i);
                  setPickerOpen(false);
                }}
              >
                <img
                  src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/thumb?idx=${i}&ds=${dataset}`}
                  alt=""
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ParamSlider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className="text-zinc-200 font-mono">{value}</span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(Array.isArray(v) ? v[0] : v)}
        className="cursor-pointer"
      />
    </div>
  );
}

function Panel({
  title,
  image,
  loading,
  isThumb,
}: {
  title: string;
  image?: string;
  loading: boolean;
  isThumb?: boolean;
}) {
  return (
    <Card className="bg-zinc-900 border-zinc-800 overflow-hidden flex flex-col">
      <div className="px-3 py-2 text-xs font-medium text-zinc-400 border-b border-zinc-800">{title}</div>
      <CardContent className="flex-1 p-0 flex items-center justify-center relative">
        {loading && (
          <div className="absolute inset-0 bg-zinc-900/80 flex items-center justify-center z-10">
            <div className="w-5 h-5 border-2 border-zinc-600 border-t-blue-500 rounded-full animate-spin" />
          </div>
        )}
        {image ? (
          <img
            src={isThumb ? image : `data:image/jpeg;base64,${image}`}
            alt={title}
            className="w-full h-full object-contain"
          />
        ) : (
          <span className="text-zinc-600 text-xs">No data</span>
        )}
      </CardContent>
    </Card>
  );
}
