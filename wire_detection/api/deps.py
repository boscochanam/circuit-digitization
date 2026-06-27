"""Shared dependencies — singletons and helpers for the API server.

Route modules import from here instead of from server.py to avoid circular imports.
"""
from __future__ import annotations



from wire_detection.data.dataset import DatasetRegistry
from wire_detection.api.cache import ImageCache
from wire_detection.api.startup import (
    load_default_config,
    ensure_synthetic_data as _ensure_synthetic_data_impl,
    log_dataset_inventory as _log_dataset_inventory_impl,
)

# ── Shared Singletons ──
registry = DatasetRegistry()
cache = ImageCache()


# ── Helpers ──

def _load_default_config() -> dict:
    """Load pipeline config from defaults.yaml."""
    return load_default_config()


def ensure_synthetic_data() -> None:
    """Generate synthetic dataset if needed."""
    _ensure_synthetic_data_impl(registry)


def log_dataset_inventory() -> None:
    """Print dataset inventory on startup."""
    _log_dataset_inventory_impl(registry)
