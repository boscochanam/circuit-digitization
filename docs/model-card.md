---
license: agpl-3.0
base_model: Ultralytics/YOLO26
pipeline_tag: object-detection
tags:
  - yolo
  - oriented-bounding-box
  - obb
  - circuit-schematics
  - electronic-design-automation
  - ultralytics
datasets:
  - johannesbayer/cghd1152
library_name: ultralytics
---

# Circuit Component Detector (YOLO26M-OBB, 16 classes)

Oriented-bounding-box detector for hand-drawn electronic circuit components. It is
Stage 1 of the pipeline in *"From Hand-Drawn Schematics to SPICE Netlists"* — it
localizes and orients components so a downstream occlusion + graph-join stage can
recover electrical connectivity.

- **Architecture:** YOLO26M-OBB (Ultralytics), fine-tuned.
- **Task:** oriented bounding-box detection.
- **Classes:** 16, merged down from CGHD-1152's 61 (variants the netlist does not
  distinguish are collapsed; 30 rare device types fold into a single `other` class).
- **Reported performance:** mAP@0.5 = 89.0% on 468 held-out scans.

## Intended use

Detecting and orienting components in scanned/photographed hand-drawn schematics as the
first stage of schematic-to-netlist digitization. The model recovers component **location,
orientation, and coarse class** — not device values. It is trained on a single hand-drawn
corpus; generalization to printed schematics or other drawing styles is unvalidated.

## Training data & attribution

Trained on **CGHD-1152**, *A Public Ground-Truth Dataset for Handwritten Circuit Diagram
Images* by Felix Thoma, Johannes Bayer, Yakun Li, and Andreas Dengel (DFKI), licensed
**CC BY 4.0** and archived at Zenodo: <https://doi.org/10.5281/zenodo.6385814>.

## License

The base weights are Ultralytics **YOLO26**, released under **AGPL-3.0**. This fine-tuned
derivative is therefore distributed under **AGPL-3.0**. If you need a non-AGPL license for
the weights, obtain an Ultralytics Enterprise License. (The surrounding pipeline *code* is
MIT and the CGHD-derived annotations are CC BY 4.0 — see the repository — but those licenses
do not extend to these weights.)

## Links

- **Code:** <https://github.com/boscochanam/circuit-digitization>
- **Archived release (Zenodo):** <https://doi.org/10.5281/zenodo.21274158> (all versions) ·
  <https://doi.org/10.5281/zenodo.21274159> (v1.0.1)

## Citation

If you use this model, please cite the paper and the software archive:

```bibtex
@article{chanam2026circuitdigitization,
  title   = {From Hand-Drawn Schematics to SPICE Netlists: A Deterministic
             Pipeline with Endpoint-Graph Wire Joining and a Human-Verified
             Connectivity Benchmark},
  author  = {Chanam, Bosco and Dcosta, Chris and Talupuri, Pranavesh Kumar and
             Chiwhane, Shwetambari and Singh, Ashay Kumar and Das, Arghadeep},
  journal = {IEEE Access},
  year    = {2026},
  note    = {Under review}
}

@software{chanam2026circuitdigitization_sw,
  title     = {Circuit Digitization: a deterministic hand-drawn-schematic-to-SPICE
               pipeline with an endpoint-graph wire join and a human-verified
               connectivity benchmark},
  author    = {Chanam, Bosco and Dcosta, Chris and Talupuri, Pranavesh Kumar and
               Chiwhane, Shwetambari and Singh, Ashay Kumar and Das, Arghadeep},
  year      = {2026},
  version   = {1.0.1},
  doi       = {10.5281/zenodo.21274158},
  url       = {https://github.com/boscochanam/circuit-digitization}
}
```

And the training dataset:

```bibtex
@inproceedings{thoma2021cghd,
  title     = {A Public Ground-Truth Dataset for Handwritten Circuit Diagram Images},
  author    = {Thoma, Felix and Bayer, Johannes and Li, Yakun and Dengel, Andreas},
  booktitle = {Proc. Int. Conf. Document Analysis and Recognition (ICDAR)},
  pages     = {20--27},
  year      = {2021},
  doi       = {10.1007/978-3-030-86198-8_2}
}
```
