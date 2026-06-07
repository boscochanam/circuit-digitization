"use client";

import { useRef, useEffect } from "react";

interface ImageGridProps {
  imageList: string[];
  imageIdx: number;
  dataset: string;
  gridCount: number;
  onSelect: (idx: number) => void;
  onScroll: () => void;
}

/**
 * Thumbnail grid for image selection — shown as a modal overlay.
 */
export default function ImageGrid({
  imageList,
  imageIdx,
  dataset,
  gridCount,
  onSelect,
  onScroll,
}: ImageGridProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      const active = scrollRef.current.querySelector(".grid-thumb-active");
      if (active) active.scrollIntoView({ block: "nearest" });
    }
  }, [imageIdx]);

  return (
    <div className="image-grid-scroll" ref={scrollRef} onScroll={onScroll}>
      {imageList.slice(0, gridCount).map((name, i) => (
        <button
          key={name}
          className={`grid-thumb ${i === imageIdx ? "grid-thumb-active" : ""}`}
          onClick={() => onSelect(i)}
        >
          <img
            src={`/api/thumb?idx=${i}&ds=${dataset}`}
            alt=""
            loading="lazy"
          />
          <span className="grid-thumb-label">{i + 1}</span>
        </button>
      ))}

      <style jsx>{`
        .image-grid-scroll {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
          gap: 4px;
          padding: 8px;
          max-height: 200px;
          overflow-y: auto;
          background: var(--white);
          border-bottom: 2px solid var(--black);
        }
        .grid-thumb {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          padding: 4px;
          border: 2px solid transparent;
          background: transparent;
          cursor: pointer;
        }
        .grid-thumb:hover {
          border-color: var(--grey-mid);
        }
        .grid-thumb-active {
          border-color: var(--black);
          background: var(--grey-light);
        }
        .grid-thumb img {
          width: 100%;
          aspect-ratio: 1;
          object-fit: cover;
          border: 1px solid var(--grey-light);
        }
        .grid-thumb-label {
          font-family: var(--font-mono), monospace;
          font-size: 9px;
          color: var(--grey-dark);
        }
      `}</style>
    </div>
  );
}
