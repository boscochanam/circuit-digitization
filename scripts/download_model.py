#!/usr/bin/env python3
"""Download and verify the component-detection model used in the paper.

Fetches the YOLO26m-OBB 16-class component detector from the public
HuggingFace repo and verifies its SHA256, so a reviewer can reproduce the
component-detection stage (and any end-to-end join eval) from a clean checkout.

Usage:
    uv run python scripts/download_model.py
    # or, to a custom location:
    uv run python scripts/download_model.py --dest models/component_detection

The download prefers plain urllib against the HuggingFace resolve URL, so it
needs no extra dependencies. If `huggingface_hub` happens to be installed it is
used as a fallback (nicer resume/caching), but it is never required.

Idempotent: if the destination file already exists and its SHA256 matches, the
download is skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

# HuggingFace repo: https://huggingface.co/boscochanam/circuit-component-detector
HF_REPO = "boscochanam/circuit-component-detector"
# Verified against the file listing on the HF repo (47.8 MB .pt weights).
MODEL_FILENAME = "yolo26m_obb_16class_aug.pt"
# Plain resolve URL — no auth, no extra deps needed.
MODEL_URL = f"https://huggingface.co/{HF_REPO}/resolve/main/{MODEL_FILENAME}"

# SHA256 recorded in docs/datasets.md (see "Trained Models" table, ~line 12).
# Keep this in sync with docs/datasets.md if the model is ever re-uploaded.
EXPECTED_SHA256 = "d700b33f90191968af9f7f2798fff5e90a3f1ea473b811adc241bc570987264d"

DEFAULT_DEST_DIR = Path("models/component_detection")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_urllib(url: str, dest: Path) -> None:
    """Stream `url` to `dest` with a progress line, using stdlib only."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "circuit-digitization/download_model"})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted HTTPS host)
        total = int(resp.headers.get("Content-Length", 0))
        read = 0
        with tmp.open("wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if total:
                    pct = 100 * read / total
                    print(f"\r  downloading {MODEL_FILENAME}: {read / 1e6:6.1f} / "
                          f"{total / 1e6:6.1f} MB ({pct:5.1f}%)", end="", flush=True)
                else:
                    print(f"\r  downloading {MODEL_FILENAME}: {read / 1e6:6.1f} MB",
                          end="", flush=True)
    print()
    tmp.replace(dest)


def _download_hf(dest_dir: Path) -> Path | None:
    """Try huggingface_hub if available; return the downloaded path or None."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return None
    print("  huggingface_hub found; using it to download")
    path = hf_hub_download(repo_id=HF_REPO, filename=MODEL_FILENAME,
                           local_dir=str(dest_dir))
    return Path(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default=str(DEFAULT_DEST_DIR),
                    help=f"destination directory (default: {DEFAULT_DEST_DIR})")
    ap.add_argument("--force", action="store_true",
                    help="re-download even if a valid file already exists")
    args = ap.parse_args()

    dest_dir = Path(args.dest)
    dest = dest_dir / MODEL_FILENAME
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Idempotent skip: file already present and correct.
    if dest.exists() and not args.force:
        print(f"  found existing {dest} — verifying SHA256...")
        actual = sha256_of(dest)
        if actual == EXPECTED_SHA256:
            print(f"  OK: {dest} already present and verified.")
            return 0
        print(f"  WARNING: existing file hash mismatch\n"
              f"    expected {EXPECTED_SHA256}\n"
              f"    actual   {actual}\n"
              f"  re-downloading...")

    # Download (huggingface_hub if present, else plain urllib).
    print(f"  fetching {MODEL_URL}")
    try:
        hf_path = _download_hf(dest_dir)
        if hf_path is not None and hf_path != dest:
            hf_path.replace(dest)
        elif hf_path is None:
            _download_urllib(MODEL_URL, dest)
    except (urllib.error.URLError, OSError) as e:
        print(f"\nERROR: download failed: {e}\n"
              f"  Check your network connection, or download manually from:\n"
              f"    {MODEL_URL}\n"
              f"  and place it at: {dest}", file=sys.stderr)
        return 1

    if not dest.exists():
        print(f"ERROR: expected file not found after download: {dest}", file=sys.stderr)
        return 1

    print("  verifying SHA256...")
    actual = sha256_of(dest)
    if actual != EXPECTED_SHA256:
        print(f"ERROR: SHA256 mismatch — the download may be corrupt or the model "
              f"was re-uploaded.\n"
              f"    expected {EXPECTED_SHA256}\n"
              f"    actual   {actual}\n"
              f"  If the model was intentionally updated, update docs/datasets.md and "
              f"EXPECTED_SHA256 in this script.", file=sys.stderr)
        return 1

    size_mb = dest.stat().st_size / 1e6
    print(f"  OK: downloaded and verified {dest} ({size_mb:.1f} MB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
