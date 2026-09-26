"""Repository and dataset path resolution.

Three kinds of path appear in this codebase, and they resolve differently.

*In-repo* paths (``output/``, ``docs/``, ``ground_truth/``) are derived from this file's
location, so a clone works anywhere on disk with no configuration.

*Committed ground truth* (wire polylines, component labels) lives in the repository. The
environment variables below exist only to point at a relocated copy; the defaults are correct
for a fresh clone.

*External corpora* (the CGHD-1152 scans, the Roboflow export) are not redistributed here.
Asking for one that is not configured raises :class:`MissingDatasetError` naming the variable
and what to point it at, rather than failing later with an empty glob.

Variable names follow the ``WIRE_*`` convention already established in
``ground_truth/README.md``. ``GT_LABELS_PATH`` predates it and is still honoured as a fallback
for :func:`gt_images_dir`, because ``docker-compose.yml`` and the tuner UI mount that variable.

See ``.env.example`` and ``docs/reproducing-the-paper.md``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

__all__ = [
    "REPO_ROOT",
    "DOCS_DIR",
    "GROUND_TRUTH_DIR",
    "MissingDatasetError",
    "expand_path",
    "output_dir",
    "gt_images_dir",
    "gt_labels_dir",
    "wire_labels_dir",
    "component_labels_dir",
    "hdc_root",
    "synthetic_root",
    "cghd_workspace",
]

#: Repository root, resolved from this file (``wire_detection/paths.py``).
REPO_ROOT: Path = Path(__file__).resolve().parents[1]

DOCS_DIR: Path = REPO_ROOT / "docs"
GROUND_TRUTH_DIR: Path = REPO_ROOT / "ground_truth"


class MissingDatasetError(RuntimeError):
    """An external dataset path is not configured, or does not exist."""


_VAR = re.compile(r"\$\{(?P<name>\w+)(?::-(?P<default>[^}]*))?\}")


def expand_path(value: str | os.PathLike[str]) -> Path:
    """Expand ``${VAR}``, ``${VAR:-default}`` and ``~`` in *value*.

    Relative results resolve against :data:`REPO_ROOT`, not the current working directory, so a
    config value behaves the same regardless of where a script is run from.

    A variable that is unset and has no default is left as the literal ``${VAR}``. The path then
    plainly cannot exist, and the unexpanded name appears verbatim in whatever error follows,
    which is more useful than quietly resolving to the repo root and globbing nothing.
    """
    unresolved = False

    def substitute(match: re.Match[str]) -> str:
        nonlocal unresolved
        resolved = os.environ.get(match["name"])
        if resolved:
            return resolved
        if match["default"] is not None:
            return match["default"]
        unresolved = True
        return match[0]

    text = os.path.expanduser(_VAR.sub(substitute, str(value)))
    path = Path(text)
    if unresolved or path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _from_env(env_var: str, default: Path) -> Path:
    """Resolve *env_var*, falling back to *default*. Never raises."""
    raw = os.environ.get(env_var)
    return expand_path(raw) if raw else default


def _require(path: Path, env_var: str, what: str, hint: str = "") -> Path:
    if not path.exists():
        raise MissingDatasetError(
            f"{what} not found at {path}.\n"
            f"Set {env_var} to the directory containing it, e.g.\n"
            f"    export {env_var}=/path/to/data\n"
            + (f"{hint}\n" if hint else "")
            + "See .env.example and docs/reproducing-the-paper.md."
        )
    return path


def output_dir() -> Path:
    """Writable directory for generated artifacts. Override with ``WIRE_OUTPUT_DIR``."""
    path = _from_env("WIRE_OUTPUT_DIR", REPO_ROOT / "output")
    path.mkdir(parents=True, exist_ok=True)
    return path


def gt_images_dir() -> Path:
    """CGHD source scans for the 134 verified images (``WIRE_GT_IMAGES``).

    Deliberately has no in-repo default: the scans are CC BY 4.0 source images and are not
    redistributed. ``GT_LABELS_PATH`` (the docker-compose mount) is honoured as a fallback,
    in which case the scans are expected under ``$GT_LABELS_PATH/images``.
    """
    explicit = os.environ.get("WIRE_GT_IMAGES")
    if explicit:
        return _require(expand_path(explicit), "WIRE_GT_IMAGES", "The CGHD source scans")
    legacy = os.environ.get("GT_LABELS_PATH")
    if legacy:
        return _require(
            expand_path(legacy) / "images", "WIRE_GT_IMAGES", "The CGHD source scans"
        )
    raise MissingDatasetError(
        "WIRE_GT_IMAGES is not set, so the CGHD source scans cannot be located.\n"
        "They are not redistributed with this repository (CC BY 4.0 source images).\n"
        "    export WIRE_GT_IMAGES=/path/to/cghd/images\n"
        "See .env.example and docs/reproducing-the-paper.md."
    )


def wire_labels_dir() -> Path:
    """Ground-truth wire polylines for the 134 verified scans (``WIRE_GT_WIRE_LABELS``).

    Committed to the repository, so this needs no configuration.
    """
    return _from_env("WIRE_GT_WIRE_LABELS", GROUND_TRUTH_DIR / "wire_labels")


#: Historical alias. The wire labels used to live in an external
#: ``labels_few_annot/labels/train/manually_verified_no_background_data/images`` tree.
gt_labels_dir = wire_labels_dir


def component_labels_dir() -> Path:
    """Component labels used for occlusion (``WIRE_COMPONENT_LABELS``).

    Committed to the repository, so this needs no configuration.
    """
    return _from_env("WIRE_COMPONENT_LABELS", GROUND_TRUTH_DIR / "component_labels")


def hdc_root() -> Path:
    """Roboflow HDC-Recognition export (``WIRE_HDC_BASE``).

    A fallback source of component labels only. Because ``ground_truth/component_labels/`` is
    committed, most workflows never need this; see ``ground_truth/README.md``.
    """
    return _require(
        _from_env("WIRE_HDC_BASE", REPO_ROOT / "roboflow_test2"),
        "WIRE_HDC_BASE",
        "The Roboflow HDC-Recognition export",
        hint="Most workflows do not need it: ground_truth/component_labels/ is committed.",
    )


def synthetic_root() -> Path:
    """Generated synthetic wire corpus (``SYNTHETIC_PATH``), default ``data/synthetic``."""
    return _require(
        _from_env("SYNTHETIC_PATH", REPO_ROOT / "data" / "synthetic"),
        "SYNTHETIC_PATH",
        "The synthetic wire corpus",
        hint="Generate it with: uv run wire-sdg --num-images 5 --output-dir data/synthetic",
    )


def cghd_workspace() -> Path:
    """Scratch directory for the one-off CGHD quality-audit artifacts.

    Holds ``cghd_reclassified.json``, ``cghd_vlm_results.json`` and similar research
    by-products (``WIRE_CGHD_WORKSPACE``, default ``data/workspace``).
    """
    return _from_env("WIRE_CGHD_WORKSPACE", REPO_ROOT / "data" / "workspace")
