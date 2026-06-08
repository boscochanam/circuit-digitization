import { useState, useEffect, useCallback, useRef } from "react";
import { listImagesAction } from "@/app/actions";
import type { DatasetMap } from "@/lib/types";

const GRID_PAGE = 60;

export type Dataset = "gt_labels" | "hdc" | "synthetic";

export function useImages(
  initial: { images: string[]; datasets: DatasetMap },
  initialIdx: number = 0,
  initialDs: string = "gt_labels",
) {
  const [dataset, setDataset] = useState<Dataset>(initialDs as Dataset);
  const [imageIdx, setImageIdx] = useState(Math.min(initialIdx, initial.images.length - 1));
  const [imageList, setImageList] = useState<string[]>(initial.images);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [datasetInfo] = useState<Record<string, { path: string; images: number }>>(() => {
    const info: Record<string, { path: string; images: number }> = {};
    for (const [k, v] of Object.entries(initial.datasets)) {
      info[k] = { path: v.path, images: v.images };
    }
    return info;
  });

  const [viewMode, setViewMode] = useState<"single" | "grid">("single");
  const [gridCount, setGridCount] = useState(GRID_PAGE);
  const gridScrollRef = useRef<HTMLDivElement>(null);

  const loadImages = useCallback(async (ds: Dataset) => {
    setListLoading(true);
    setListError(null);
    try {
      const list = await listImagesAction(ds);
      setImageList(list);
      setImageIdx(0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load images";
      setListError(msg);
      setImageList([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  const skipInitialList = useRef(true);
  useEffect(() => {
    if (skipInitialList.current) {
      skipInitialList.current = false;
      return;
    }
    loadImages(dataset);
  }, [dataset, loadImages]);

  useEffect(() => {
    if (viewMode === "grid") {
      setGridCount(GRID_PAGE);
      requestAnimationFrame(() => {
        if (gridScrollRef.current) {
          const active = gridScrollRef.current.querySelector(".grid-thumb-active");
          if (active) active.scrollIntoView({ block: "center", behavior: "auto" });
        }
      });
    }
  }, [viewMode]);

  const handleGridScroll = useCallback((e?: { currentTarget: HTMLElement }) => {
    // use the scroll event's element — ImageGrid owns its own scroll ref, so the
    // module-level gridScrollRef was always null and "load more" never fired
    // (you were stuck on the first page of thumbnails for large datasets).
    const el = e?.currentTarget ?? gridScrollRef.current;
    if (!el) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 300) {
      setGridCount((prev) => Math.min(prev + GRID_PAGE, imageList.length));
    }
  }, [imageList.length]);

  const imageCount = imageList.length || datasetInfo[dataset]?.images || 0;

  return {
    dataset,
    setDataset,
    imageIdx,
    setImageIdx,
    imageList,
    pickerOpen,
    setPickerOpen,
    listLoading,
    listError,
    datasetInfo,
    imageCount,
    viewMode,
    setViewMode,
    gridCount,
    gridScrollRef,
    handleGridScroll,
  };
}
