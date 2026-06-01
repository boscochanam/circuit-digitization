"""Shared dependencies — re-exports from server for route modules.

All shared state (registry, cache) and helpers live in server.py so that
existing test mock paths (wire_detection.api.server.registry etc.) continue
to work. Route modules should use ``import wire_detection.api.server as _server``
and access ``_server.registry``, ``_server.cache`` etc. so that test patches
propagate correctly.
"""
import wire_detection.api.server as _server

registry = _server.registry
cache = _server.cache
_load_default_config = _server._load_default_config
_ensure_synthetic_data = _server._ensure_synthetic_data
_log_dataset_inventory = _server._log_dataset_inventory
