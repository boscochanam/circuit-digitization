import HomeClient from "./HomeClient";
import { fetchBackend } from "@/lib/api";
import type { HomeInitialData } from "@/lib/types";

export const dynamic = "force-dynamic";
async function loadInitialData(): Promise<HomeInitialData> {
  const [images, presets, datasets] = await Promise.all([
    fetchBackend<string[]>("/api/list?ds=gt_labels"),
    fetchBackend<HomeInitialData["presets"]>("/api/presets"),
    fetchBackend<HomeInitialData["datasets"]>("/api/datasets"),
  ]);
  return {
    images: Array.isArray(images) ? images : [],
    presets,
    datasets,
  };
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ idx?: string; ds?: string }>;
}) {
  const params = await searchParams;
  const initialIdx = params.idx ? Math.max(0, parseInt(params.idx, 10) || 0) : 0;
  const initialDs = params.ds || "gt_labels";
  let initial: HomeInitialData;
  try {
    initial = await loadInitialData();
  } catch (err) {
    console.error("Failed to load initial data from backend:", err);
    initial = { images: [], presets: {}, datasets: {} };
  }
  return <HomeClient initial={initial} initialIdx={initialIdx} initialDs={initialDs} />;
}
