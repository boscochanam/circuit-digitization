import { useState, useEffect, useCallback, useRef } from "react";
import { runPipelineAction } from "@/app/actions";
import type { PipelineResult, PresetMap } from "@/lib/types";

const DEFAULT_PRESET_PARAMS = {
  sauvola_k: 0.285,
  sauvola_window: 67,
  close_kernel: 3,
  ccl_min_area: 28,
  dedup_angle: 10,
  dedup_dist: 18,
  anchor_endpoint_dist: 12.0,
  anchor_link_dist: 8.0,
};

export function usePipeline(
  initial: { presets: PresetMap },
  imageIdx: number,
  dataset: string,
  imageCount: number,
) {
  const [loading, setLoading] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [preset, setPreset] = useState<string>("best_candidate_v4");
  const [presets, setPresets] = useState<PresetMap>(initial.presets);
  const [presetParams, setPresetParams] = useState<Record<string, number>>(DEFAULT_PRESET_PARAMS);

  const [result, setResult] = useState<PipelineResult | null>(null);

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
    if (initial.presets.best_candidate_v4?.params) {
      setPresetParams(initial.presets.best_candidate_v4.params);
    }
  }, [initial.presets]);

  useEffect(() => {
    const p = presets[preset];
    if (p?.params) setPresetParams(p.params);
    else if (preset !== "legacy_threshold") setPresetParams(DEFAULT_PRESET_PARAMS);
  }, [preset, presets]);

  const doRun = useCallback(
    (idx: number, p: typeof params, pr: string, pp: Record<string, number>) => {
      setLoading(true);
      setPipelineError(null);
      const body = pr === "legacy_threshold" ? p : pp;
      runPipelineAction(idx, dataset, body, pr)
        .then((data) => { setResult(data); setLoading(false); })
        .catch((err) => {
          console.error("Pipeline error:", err);
          setPipelineError(err instanceof Error ? err.message : "Pipeline failed");
          setResult(null);
          setLoading(false);
        });
    },
    [dataset],
  );

  // Debounce: param slider changes fire after 300ms idle; image/preset changes run immediately.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastImageRef = useRef(imageIdx);
  const lastPresetRef = useRef(preset);

  useEffect(() => {
    if (imageCount <= 0) return;

    const imageChanged = imageIdx !== lastImageRef.current;
    const presetChanged = preset !== lastPresetRef.current;
    lastImageRef.current = imageIdx;
    lastPresetRef.current = preset;

    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }

    if (imageChanged || presetChanged) {
      // Immediate run for image/preset changes
      doRun(imageIdx, params, preset, presetParams);
    } else {
      // Debounced run for param slider changes
      debounceRef.current = setTimeout(() => {
        debounceRef.current = null;
        doRun(imageIdx, params, preset, presetParams);
      }, 300);
    }
  }, [imageIdx, params, dataset, preset, presetParams, imageCount, doRun]);

  const setParam = (key: string, value: number | string) =>
    setParams((prev) => ({ ...prev, [key]: value }));

  const setPresetParam = (key: string, value: number) =>
    setPresetParams((prev) => ({ ...prev, [key]: value }));

  const isLegacy = preset === "legacy_threshold";

  return {
    loading,
    pipelineError,
    preset,
    setPreset,
    presets,
    presetParams,
    setPresetParam,
    result,
    params,
    setParam,
    isLegacy,
  };
}
