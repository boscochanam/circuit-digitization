import HomeClient from "./HomeClient";
import { fetchBackend } from "@/lib/api";
import type { HomeInitialData } from "@/lib/types";

export const dynamic = "force-dynamic";
async function loadInitialData(ds: string): Promise<HomeInitialData> {
  const [images, presets, datasets] = await Promise.all([
    // Fetch the image list for the REQUESTED dataset, not always gt_labels.
    // Otherwise a deep link like ?ds=hdc loaded the 94-image gt_labels list and
    // clamped the index to it, so most of HDC's ~1680 images were unreachable.
    fetchBackend<string[]>(`/api/list?ds=${encodeURIComponent(ds)}`),
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
    initial = await loadInitialData(initialDs);
  } catch (err) {
    console.error("Failed to load initial data from backend:", err);
    initial = { images: [], presets: {}, datasets: {} };
  }
  return <HomeClient initial={initial} initialIdx={initialIdx} initialDs={initialDs} />;
}
