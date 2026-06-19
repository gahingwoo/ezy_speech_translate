"""Centralised configuration loading.

Single source of truth for `get_config(*keys, default=None)` used by user
and admin servers. Tries the encrypted SecureConfig first, falls back to a
plain YAML reader. Removes the ~40-line copy/paste that previously lived at
the top of both server.py files.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import yaml

_log = logging.getLogger("config_loader")

# Resolve project root: <repo>/app/core/config.py -> <repo>
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config", "config.yaml")


class _YamlFallback:
    """Plain YAML config (used when secure_loader is unavailable)."""

    def __init__(self, path: str) -> None:
        self._path = path
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.data = yaml.safe_load(fh) or {}
        except FileNotFoundError:
            _log.error("Configuration file not found at %s", path)
            self.data = {}

    def get(self, *keys: str, default: Any = None) -> Any:
        val: Any = self.data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
                if val is None:
                    return default
            else:
                return default
        return val if val is not None else default


def _build_loader():
    # Ensure project root is on sys.path so `secure_loader` (root-level module) imports.
    if _BASE_DIR not in sys.path:
        sys.path.insert(0, _BASE_DIR)
    try:
        from secure_loader import SecureConfig  # type: ignore
        loader = SecureConfig(_CONFIG_PATH)
        _log.info("Loaded encrypted configuration via secure_loader")
        return loader
    except Exception as exc:  # pragma: no cover - depends on deploy state
        _log.warning("Secure loader unavailable (%s); using YAML fallback", exc)
        return _YamlFallback(_CONFIG_PATH)


config_loader = _build_loader()


def get_config(*keys: str, default: Any = None) -> Any:
    """Look up a (possibly nested) config value by key path."""
    return config_loader.get(*keys, default=default)


def ensure_runtime_secret(secrets_field: str, config_keys: tuple[str, ...]) -> str:
    """Return a strong secret for `config_keys`, generating+persisting if needed.

    Delegates to SecureConfig.ensure_secret (which persists into secrets.key)
    when the encrypted loader is active. If only the plain-YAML fallback is
    available (secure_loader unavailable), a strong per-process secret is
    generated and injected so the server never runs on a forgeable default.
    """
    loader = config_loader
    if hasattr(loader, "ensure_secret"):
        try:
            return loader.ensure_secret(secrets_field, tuple(config_keys))
        except Exception as exc:  # pragma: no cover - defensive
            _log.warning("ensure_secret(%s) failed (%s); using ephemeral secret",
                         secrets_field, exc)

    import secrets as _secrets
    value = _secrets.token_urlsafe(48)
    try:
        node = loader.data  # type: ignore[attr-defined]
        for k in config_keys[:-1]:
            nxt = node.get(k)
            if not isinstance(nxt, dict):
                nxt = {}
                node[k] = nxt
            node = nxt
        node[config_keys[-1]] = value
    except Exception:
        pass
    _log.warning("Persistent secret store unavailable; '%s' is ephemeral for this process",
                 secrets_field)
    return value


__all__ = ["get_config", "config_loader", "ensure_runtime_secret"]
