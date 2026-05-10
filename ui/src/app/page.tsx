"use client";

import { useState, useEffect, useCallback } from "react";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { listImages, runPipeline, fetchDatasets } from "@/lib/api";

const DATASETS = ["hand_drawn", "synthetic", "database"] as const;
type Dataset = (typeof DATASETS)[number];

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [dataset, setDataset] = useState<Dataset>("hand_drawn");
  const [imageIdx, setImageIdx] = useState(0);
  const [imageList, setImageList] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [datasetInfo, setDatasetInfo] = useState<Record<string, { path: string; images: number }>>({});
  const [result, setResult] = useState<{
    line_count: number; blob_count: number; elapsed_ms: number;
    overlay: string; threshold: string; dilated: string;
  } | null>(null);

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

  const loadImages = useCallback(async (ds: Dataset) => {
    setListLoading(true);
    setListError(null);
    try {
      const list = await listImages(ds);
      console.log(`[WireDetection] Loaded ${list.length} images for dataset "${ds}"`);
      setImageList(list);
      setImageIdx(0);
    } catch (err: any) {
      console.error("[WireDetection] Failed to load images:", err);
      setListError(err.message || "Failed to load images");
      setImageList([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadImages(dataset);
  }, [dataset, loadImages]);

  useEffect(() => {
    fetchDatasets()
      .then((info) => {
        const simplified: Record<string, { path: string; images: number }> = {};
        for (const [k, v] of Object.entries(info)) {
          simplified[k] = { path: v.path, images: v.images };
        }
        setDatasetInfo(simplified);
      })
      .catch((err) => console.error("[WireDetection] fetchDatasets error:", err));
  }, []);

  const doRun = useCallback(
    (idx: number, p: typeof params) => {
      setLoading(true);
      runPipeline(idx, dataset, p)
        .then((data) => {
          setResult(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error("[WireDetection] Pipeline error:", err);
          setLoading(false);
        });
    },
    [dataset],
  );

  useEffect(() => {
    if (imageList.length > 0) doRun(imageIdx, params);
  }, [imageIdx, params, dataset, imageList, doRun]);

  const setParam = (key: string, value: number | string) =>
    setParams((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      {/* ── Sidebar ── */}
      <aside className="w-80 flex flex-col border-r border-zinc-800 bg-zinc-900 p-4 gap-3 overflow-y-auto">
        <h1 className="text-lg font-bold tracking-tight">Wire Detection Tuner</h1>

        {/* Dataset selector */}
        <div>
          <label className="text-xs text-zinc-400 mb-1 block">Dataset</label>
          <div className="flex gap-1 flex-wrap">
            {DATASETS.map((d) => (
              <Button
                key={d}
                variant={dataset === d ? "default" : "outline"}
                size="sm"
                className="flex-1 min-w-[80px]"
                onClick={() => setDataset(d)}
              >
                {d === "hand_drawn" ? "Hand Drawn" : d === "synthetic" ? "Synthetic" : "Database"}
              </Button>
            ))}
          </div>
        </div>

        {/* Image picker button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setPickerOpen(true)}
          className="h-20 p-1 relative"
          disabled={listLoading || imageList.length === 0}
        >
          {imageList[imageIdx] ? (
            <img
              src={`${API_URL}/api/thumb?idx=${imageIdx}&ds=${dataset}`}
              alt=""
              className="w-full h-full object-contain rounded"
            />
          ) : listLoading ? (
            <span className="text-zinc-400 text-xs">Loading...</span>
          ) : (
            <span className="text-zinc-400 text-xs">No images</span>
          )}
        </Button>

        {/* Diagnostics */}
        <div className="text-[10px] text-zinc-500 font-mono space-y-0.5 bg-zinc-950/50 p-2 rounded border border-zinc-800">
          <div>API: {API_URL}</div>
          <div>Dataset: {dataset}</div>
          <div>Images: {imageList.length}</div>
          {datasetInfo[dataset] && (
            <div>Backend: {datasetInfo[dataset].images} imgs @ {datasetInfo[dataset].path}</div>
          )}
          {listError && <div className="text-red-400">Error: {listError}</div>}
        </div>

        <Separator />

        {/* Threshold mode */}
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
          <Button
            variant={params.thresh_mode === "adaptive" ? "default" : "outline"}
            size="sm"
            className="flex-1"
            onClick={() => setParam("thresh_mode", "adaptive")}
          >
            Adaptive
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
        <Panel title="Source" image={`${API_URL}/api/thumb?idx=${imageIdx}&ds=${dataset}`} loading={false} isThumb />
      </main>

      {/* ── Image Picker Dialog ── */}
      <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <DialogContent
          className="bg-zinc-950 border-zinc-800 p-6"
          style={{ maxWidth: "calc(100vw - 2rem)", maxHeight: "calc(100vh - 2rem)", width: "100%", height: "100%" }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-zinc-400">
              {imageList.length} images in "{dataset}"
            </span>
            {listError && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-400">{listError}</span>
                <Button size="sm" variant="outline" onClick={() => loadImages(dataset)}>
                  Retry
                </Button>
              </div>
            )}
          </div>
          <div className="grid grid-cols-5 gap-4 overflow-y-auto max-h-[85vh]">
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
                  src={`${API_URL}/api/thumb?idx=${i}&ds=${dataset}`}
                  alt=""
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
          {imageList.length === 0 && !listLoading && (
            <div className="text-center text-zinc-500 py-10">
              No images found.
              <br />
              <span className="text-xs">
                Check that the backend is running and datasets are mounted.
              </span>
            </div>
          )}
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
