"""Vertical plug-in framework (task 5.2).

A vertical describes a target industry (seed sources, reference pipelines, target
apps). Verticals come from three layers, merged in priority order:

1. Core verticals in ``config/business/verticals.yaml`` (shipped defaults).
2. Plug-in files in ``config/verticals/*.yaml`` (drop-in extensions, committed).
3. Runtime registrations persisted to Redis (added via the API at runtime).

This lets new industries be added without code changes — either by dropping a
YAML plug-in into ``config/verticals/`` or by POSTing to the orchestrator.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("id", "name")
REDIS_KEY = "speedflow:verticals:custom"


def _config_base() -> Path:
    base = Path(os.environ.get("CONFIG_PATH", "/app/config"))
    if base.exists():
        return base
    return Path(__file__).parent.parent.parent / "config"


def _load_core() -> dict[str, dict]:
    base = _config_base()
    path = base / "business" / "verticals.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    verticals = data.get("verticals", {}) or {}
    for vid, spec in verticals.items():
        spec.setdefault("id", vid)
        spec["source"] = "core"
    return verticals


def _load_plugins() -> dict[str, dict]:
    """Load every vertical defined under config/verticals/*.yaml."""
    out: dict[str, dict] = {}
    plugin_dir = _config_base() / "verticals"
    if not plugin_dir.is_dir():
        return out
    for path in sorted(plugin_dir.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("failed to load vertical plugin %s: %s", path, exc)
            continue
        # A plugin file may hold one vertical (flat dict) or many (under `verticals`).
        entries = data.get("verticals") if isinstance(data.get("verticals"), dict) else {data.get("id", path.stem): data}
        for vid, spec in entries.items():
            if not isinstance(spec, dict):
                continue
            spec.setdefault("id", vid)
            spec["source"] = "plugin"
            out[spec["id"]] = spec
    return out


class VerticalRegistry:
    """Merged, extensible registry of verticals with runtime registration."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    def _load_custom(self) -> dict[str, dict]:
        if self._redis is None:
            return {}
        try:
            raw = self._redis.hgetall(REDIS_KEY) or {}
        except Exception as exc:
            logger.warning("vertical custom load failed: %s", exc)
            return {}
        custom: dict[str, dict] = {}
        for k, v in raw.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            try:
                spec = json.loads(val)
                spec.setdefault("id", key)
                spec["source"] = "runtime"
                custom[key] = spec
            except Exception:
                continue
        return custom

    def list_all(self) -> dict[str, dict]:
        merged: dict[str, dict] = {}
        merged.update(_load_core())
        merged.update(_load_plugins())
        merged.update(self._load_custom())
        return merged

    def get(self, vertical_id: str) -> dict | None:
        return self.list_all().get(vertical_id)

    def validate(self, spec: dict[str, Any]) -> None:
        for field in REQUIRED_FIELDS:
            if not spec.get(field):
                raise ValueError(f"vertical is missing required field: {field}")

    def register(self, spec: dict[str, Any]) -> dict:
        """Persist a runtime vertical plug-in (Redis-backed)."""
        self.validate(spec)
        vid = spec["id"]
        spec.setdefault("priority", 99)
        spec.setdefault("seed_sources", [])
        spec.setdefault("target_apps", [])
        if self._redis is None:
            raise RuntimeError("no redis backend available for runtime registration")
        self._redis.hset(REDIS_KEY, vid, json.dumps(spec))
        spec["source"] = "runtime"
        logger.info("registered runtime vertical: %s", vid)
        return spec

    def unregister(self, vertical_id: str) -> bool:
        if self._redis is None:
            return False
        return bool(self._redis.hdel(REDIS_KEY, vertical_id))
