from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from shutil import copytree

from wire_detection.vlm.cli import cmd_audit_pipeline


def test_audit_pipeline_rebuilds_checked_in_outputs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = repo_root / "docs" / "experiments" / "data"
    work_dir = tmp_path / "data"
    copytree(source_dir, work_dir)

    args = Namespace(results_dir=str(work_dir), output_audit=True)
    cmd_audit_pipeline(args)

    reclassified = json.loads((work_dir / "cghd_reclassified.json").read_text())
    audit = json.loads((work_dir / "cghd_final_audit.json").read_text())

    assert len(reclassified) == 330
    assert audit["total_images_sampled"] == 330
    assert audit["total_drafters"] == 33
    assert audit["recommended_keep"] == [
        "drafter_2",
        "drafter_7",
        "drafter_9",
        "drafter_12",
        "drafter_14",
        "drafter_22",
    ]
