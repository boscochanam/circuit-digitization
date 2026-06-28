"""Batch VLM connectivity eval via opencode-go zen API (resumable)."""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

PROMPT_TEMPLATE = (
    "Analyze the hand-drawn circuit at {image_path}. Read the image. "
    "Components are in numbered red boxes. Two components share a net when a continuous "
    "wire path joins their terminals (through wires, corners, T-junctions, and dots, but "
    "NOT through another component). A net is the set of box numbers whose terminals meet "
    "at one electrical node; a two-terminal component appears in two nets. Trace the wires. "
    'Return ONLY a JSON object on one line: {{"nets": [[box numbers on a node], ...]}}'
)

DEFAULT_IMAGES = (
    "docs/research/session-artifacts/3863951f-0f13-4730-8c2c-4af7f3011b71/scratchpad/vlm_clean"
)
DEFAULT_OUT = "docs/research/experiments/vlm_mimo_v25_responses_n31.json"
ZEN_URL = "https://opencode.ai/zen/go/v1/chat/completions"
AUTH_PATH = Path.home() / ".local/share/opencode/auth.json"


def _load_key() -> str:
    return json.loads(AUTH_PATH.read_text())["opencode-go"]["key"]


def _call(image_path: Path, model: str, key: str, retries: int = 3) -> str:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    prompt = PROMPT_TEMPLATE.format(image_path=image_path)
    body = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "max_tokens": 8192,
        "temperature": 0,
    }
    req = urllib.request.Request(
        ZEN_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "opencode/1.17.11",
        },
        method="POST",
    )
    last_err = ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                out = json.load(resp)
            msg = out["choices"][0]["message"]
            text = msg.get("content") or msg.get("reasoning") or ""
            if not text.strip():
                raise RuntimeError("empty model response")
            return text
        except urllib.error.HTTPError as e:
            last_err = e.read().decode()
            if e.code in (429, 502, 503) and attempt + 1 < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {last_err[:500]}") from e
        except urllib.error.URLError as e:
            last_err = str(e)
            if attempt + 1 < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(last_err)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default=DEFAULT_IMAGES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--model", default="mimo-v2.5")
    ap.add_argument("--provider-label", default="opencode-go/mimo-v2.5")
    args = ap.parse_args()

    img_dir = Path(args.images)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta: dict = {}
    responses: dict[str, str] = {}
    if out_path.exists():
        meta = json.loads(out_path.read_text())
        responses = meta.get("responses", {})

    images = sorted(img_dir.glob("*.png"))
    key = _load_key()
    done = 0
    for img in images:
        img_id = img.stem
        if img_id in responses and responses[img_id]:
            continue
        print(f"[{done + 1}/{len(images)}] {img_id} ...", flush=True)
        responses[img_id] = _call(img, args.model, key)
        done += 1
        meta = {
            "model": args.provider_label,
            "api": ZEN_URL,
            "prompt_template": PROMPT_TEMPLATE,
            "n_total": len(images),
            "n_done": len(responses),
            "responses": responses,
        }
        out_path.write_text(json.dumps(meta, indent=2))

    print(f"Wrote {out_path} ({len(responses)}/{len(images)} images)")


if __name__ == "__main__":
    main()
