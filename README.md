# Circuit Digitization: Hand-Drawn Schematics to SPICE Netlists

A deterministic pipeline that converts scanned, hand-drawn circuit schematics into SPICE
netlists. The pipeline runs component detection, an occlusion-first wire extractor, an
endpoint-graph join that resolves which terminals are electrically the same net, and netlist
emission, with no learned connectivity model in the loop. Alongside the pipeline, this
repository publishes the first human-verified, net-level connectivity benchmark for hand-drawn
circuits (31 images from CGHD-1152), so connectivity accuracy can be measured directly rather
than inferred from downstream tasks.

The pipeline recovers circuit *topology*, not component values. Emitted netlists are
structurally valid by construction, and simulation accuracy is reported on the synthetic suite,
where values are known. Reading values off a scan needs an OCR stage that this pipeline does
not have.

![Pipeline and results overview](paper/ieee-paper/figures/graphical_abstract.jpg)

## Paper

This repository contains the code and benchmark for:

> **From Hand-Drawn Schematics to SPICE Netlists: A Deterministic Pipeline with Endpoint-Graph
> Wire Joining and a Human-Verified Connectivity Benchmark.**
> Under review at IEEE Access (2026).

### How to cite

```bibtex
@article{chanam2026handdrawn,
  title   = {From Hand-Drawn Schematics to SPICE Netlists: A Deterministic Pipeline
             with Endpoint-Graph Wire Joining and a Human-Verified Connectivity Benchmark},
  author  = {Chanam, Bosco and Dcosta, Chris and Talupuri, Pranavesh Kumar and
             Chiwhane, Shwetambari and Singh, Ashay Kumar and Das, Arghadeep},
  year    = {2026},
  note    = {Under review at IEEE Access}
}
```

## Authors

| Author | ORCID | Affiliation |
|---|---|---|
| Bosco Chanam | [0009-0009-2527-0967](https://orcid.org/0009-0009-2527-0967) | Symbiosis Institute of Technology, Pune, India |
| Chris Dcosta | [0009-0007-7295-0573](https://orcid.org/0009-0007-7295-0573) | Symbiosis Institute of Technology, Pune, India |
| Pranavesh Kumar Talupuri | [0009-0005-8974-2012](https://orcid.org/0009-0005-8974-2012) | University of Southern California, Los Angeles, CA, USA |
| Shwetambari Chiwhane | [0000-0002-3534-9654](https://orcid.org/0000-0002-3534-9654) | Symbiosis Institute of Technology, Pune, India |
| Ashay Kumar Singh | [0009-0004-9105-7383](https://orcid.org/0009-0004-9105-7383) | Symbiosis Institute of Technology, Pune, India |
| Arghadeep Das | [0009-0000-9207-7694](https://orcid.org/0009-0000-9207-7694) | Symbiosis Institute of Technology, Pune, India |

Machine-readable author metadata is in [`CITATION.cff`](CITATION.cff).

## Headline results

All connectivity numbers are micro-F1 on the 31-image human-verified net-level benchmark
(`ground_truth/real_nets_verified.json`), over identical detected wires unless noted. Full
provenance for every figure is in [`docs/research/experiments/SUMMARY.md`](docs/research/experiments/SUMMARY.md).

| Measurement | Score |
|---|---|
| Component detection mAP@0.5 (16 classes, 468 held-out scans) | 89.0% |
| Wire-detection F1 (134 CGHD scans) | 0.976 |
| Connectivity micro-F1 — ours (scale-relative base + completion) | 0.890 |
| Connectivity micro-F1 — prior completion default | 0.829 |
| Connectivity micro-F1 — Hough + proximity | 0.805 |
| Connectivity micro-F1 — radius union-find | 0.667 |
| Connectivity micro-F1 — connected-components net tracing | 0.624 |
| Connectivity micro-F1 — frontier VLM reference | 0.923 |
| Synthetic suite at maximum severity — ours vs. radius baseline | 0.95 vs. 0.36 |

The VLM reference (0.923) is statistically indistinguishable from our join: the paired
difference has a bootstrap 95% CI of [−0.009, +0.078], which includes zero. It costs two to
three orders of magnitude more per image, returns free-form text rather than a structured
netlist, and offers no structural guarantee against electrically invalid output. Running the
join on perfect wire labels leaves micro-F1 unchanged at 0.890, so connectivity, not wire
detection, is the remaining bottleneck.

Detector training logs, per-class recall, and the full 61-to-16 class map are committed under
[`docs/research/experiments/detector/`](docs/research/experiments/detector/README.md).

## Quickstart

Requires Python >= 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv venv && uv sync
```

Download the component-detection model weights (verifies SHA256 and installs into
`models/component_detection/`):

```bash
uv run scripts/download_model.py
```

This fetches `yolo26m_obb_16class_aug.pt` from
[huggingface.co/boscochanam/circuit-component-detector](https://huggingface.co/boscochanam/circuit-component-detector).

Run a zero-external-data synthetic demo (generates images and line labels, no dataset needed):

```bash
uv run wire-sdg --num-images 5 --output-dir data/synthetic_demo --seed 0
```

Real-image evaluation additionally needs the CGHD-1152 dataset, *A Public Ground-Truth Dataset
for Handwritten Circuit Diagram Images*, by Felix Thoma, Johannes Bayer, and Yakun Li (DFKI),
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and archived at
[doi:10.5281/zenodo.6385814](https://doi.org/10.5281/zenodo.6385814). Mirror on Kaggle:
[kaggle.com/datasets/johannesbayer/cghd1152](https://www.kaggle.com/datasets/johannesbayer/cghd1152).

The scans are not redistributed here, so point the code at your copy. Nothing in the repository
hardcodes an absolute path:

```bash
cp .env.example .env      # then edit, or export the variable directly
export WIRE_GT_IMAGES=/path/to/cghd/images
```

That is the only variable real-image evaluation requires: the ground-truth wire polylines and
component labels are committed under `ground_truth/`, so the Roboflow export is not needed. An
unset variable produces an error naming it, rather than an empty result, and synthetic-only
workflows need no configuration at all. See [`docs/datasets.md`](docs/datasets.md) for the rest.

## Reproducing the paper

See [`docs/reproducing-the-paper.md`](docs/reproducing-the-paper.md) for the full walkthrough.
The key artifacts are:

- `ground_truth/real_nets_verified.json` — the 31-image human-verified net-level ground truth.
- `wire_detection/benchmark/` — evaluation scripts, including the join-strategy benchmarks,
  connected-component and Hough baselines, the detection ceiling, and bootstrap confidence
  intervals.
- `docs/research/experiments/*.json` — the committed result artifacts backing every headline
  number, indexed by [`docs/research/experiments/SUMMARY.md`](docs/research/experiments/SUMMARY.md).

## Command-line tools

Installed as console scripts by `uv sync`:

| Command | Description |
|---|---|
| `wire-pipeline` | Run the full pipeline on a single image |
| `wire-sdg` | Generate a synthetic wire dataset |
| `wire-eval` | Evaluate detections against ground truth |
| `wire-sweep` | Run a parameter sweep over the pipeline |
| `wire-tune` | Start the interactive tuner API server (FastAPI) |
| `wire-vlm` | VLM-based quality assessment (classify, sweep, audit) |
| `wire-benchmark-exp` | Run the wire-detection experiment harness |
| `wire-benchmark-quality` | Bridge CGHD quality-audit signals to benchmark performance |
| `wire-benchmark-learned` | Train the lightweight learned wire-mask branch |

Pass `--help` to any command for its arguments.

## Interactive tuner

A FastAPI backend plus a Next.js UI for stepping through images, inspecting detected topology,
hand-editing wire connections, and watching edits propagate into the netlist and simulation.

```bash
uv run wire-tune                  # backend API
cd ui && pnpm install && pnpm dev # UI on http://localhost:4200
```

See [`ui/README.md`](ui/README.md) for details.

## Project structure

```
wire_detection/     Python backend
  pipeline/         Single-image pipeline
  core/             Netlist, join strategies, join graph, SPICE, simulator, mapping
  benchmark/        Evaluation and baseline scripts
  sdg/  synthgt/    Synthetic data / ground-truth generators
  evaluate/  experiment/   Detection eval and parameter sweeps
  vlm/              VLM quality classifier
  api/              FastAPI routes
ui/                 Next.js tuner UI
ground_truth/       Human-verified net-level GT
models/             Component-detection weights (downloaded, gitignored)
docs/               MkDocs documentation and research logs
paper/ieee-paper/   IEEE Access manuscript source
```

## Documentation

Browse the docs locally:

```bash
uv run mkdocs serve
```

Source lives under [`docs/`](docs/). Historical research-log material from earlier revisions of
this README is archived in [`docs/research/readme-archive.md`](docs/research/readme-archive.md).

## Tests

```bash
uv run pytest wire_detection/tests/ -q
```

## License

Two licenses apply:

- **Source code, documentation, and net annotations** — MIT, see [`LICENSE.txt`](LICENSE.txt).
- **Overlay images** under `ground_truth/net_gt_ui_overlays/` — CC BY 4.0. They are adaptations
  of [CGHD-1152](https://doi.org/10.5281/zenodo.6385814) (Thoma, Bayer, and Li, DFKI) and remain
  under the source dataset's license. See [`ground_truth/LICENSE`](ground_truth/LICENSE) for the
  required attribution and a statement of the modifications made.

## Contact

Questions about the code or the benchmark are best raised as an issue on the
[repository](https://github.com/boscochanam/circuit-digitization).

- Bosco Chanam — GitHub [@boscochanam](https://github.com/boscochanam)
- Chris Dcosta — chrisdcosta777@gmail.com, chris.dcosta.btech2021@sitpune.edu.in
</content>
