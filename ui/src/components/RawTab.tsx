"use client";

import { useState } from "react";
import type { PipelineResult } from "@/lib/types";

interface RawTabProps {
  result: PipelineResult | null;
}

/**
 * Bottom-panel Raw tab: formatted JSON view of the pipeline result for debugging.
 */
export default function RawTab({ result }: RawTabProps) {
  const [copied, setCopied] = useState(false);

  // Build display JSON — exclude heavy base64 image fields for readability
  const displayResult = result
    ? {
        line_count: result.line_count,
        blob_count: result.blob_count,
        elapsed_ms: result.elapsed_ms,
        preset: result.preset,
        params: result.params,
        components: result.components,
        lines: result.lines,
        // Omit overlay/threshold/dilated (base64 blobs)
      }
    : null;

  const json = displayResult ? JSON.stringify(displayResult, null, 2) : "{}";

  const handleCopy = async () => {
    const fullJson = result ? JSON.stringify(result, null, 2) : "{}";
    try {
      await navigator.clipboard.writeText(fullJson);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard not available */
    }
  };

  if (!result) {
    return (
      <div className="raw-tab">
        <div className="viewport-empty">No pipeline result — run detection first</div>
      </div>
    );
  }

  return (
    <div className="raw-tab">
      <div className="netlist-section">
        <div className="netlist-section-title">
          Pipeline Result (JSON)
          <button className="netlist-copy-btn" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <pre className="netlist-code">{json}</pre>
      </div>
    </div>
  );
}
