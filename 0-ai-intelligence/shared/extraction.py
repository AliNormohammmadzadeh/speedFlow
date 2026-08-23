"""Declarative extraction profiles — match URLs/requirements to crawl + extract config."""

from __future__ import annotations

import fnmatch
from typing import Any
from urllib.parse import urlparse

from shared.utils import load_yaml

_PROFILES_CACHE: dict[str, Any] | None = None


def _profiles_config() -> dict[str, Any]:
    global _PROFILES_CACHE
    if _PROFILES_CACHE is None:
        _PROFILES_CACHE = load_yaml("extraction/profiles.yaml") or {}
    return _PROFILES_CACHE


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return ""


def _host_matches(host: str, patterns: list[str]) -> bool:
    host = host.lower()
    for pattern in patterns:
        p = pattern.lower()
        if p.startswith("*"):
            if fnmatch.fnmatch(host, p):
                return True
        elif p in host or host == p or host.endswith("." + p):
            return True
    return False


def _keyword_matches(text: str, keywords: list[str]) -> bool:
    blob = text.lower()
    return any(k.lower() in blob for k in keywords)


def match_extraction_profile(
    requirement: str,
    urls: list[str] | None = None,
    hints: dict[str, Any] | None = None,
) -> str | None:
    """Return best-matching profile id or None."""
    hints = hints or {}
    urls = urls or []
    if hints.get("url"):
        urls = [hints["url"]] + [u for u in urls if u != hints["url"]]

    blob = " ".join([requirement, hints.get("url", ""), " ".join(urls)])
    hosts = [_host_from_url(u) for u in urls if u]

    host_matches: list[tuple[int, str]] = []
    keyword_matches: list[tuple[int, str]] = []

    for profile_id, profile in (_profiles_config().get("profiles") or {}).items():
        match_cfg = profile.get("match") or {}
        host_score = 0
        keyword_score = 0

        for pattern in match_cfg.get("host_patterns") or []:
            if any(_host_matches(h, [pattern]) for h in hosts):
                host_score = 10

        if match_cfg.get("requirement_keywords") and _keyword_matches(blob, match_cfg["requirement_keywords"]):
            keyword_score = 5
            if hosts and not match_cfg.get("host_patterns"):
                host_specific = any(
                    _host_matches(h, (p.get("match") or {}).get("host_patterns") or [])
                    for h in hosts
                    for p in (_profiles_config().get("profiles") or {}).values()
                )
                if host_specific:
                    keyword_score = 0

        if host_score:
            host_matches.append((host_score, profile_id))
        elif keyword_score:
            keyword_matches.append((keyword_score, profile_id))

    if host_matches:
        host_matches.sort(reverse=True)
        return host_matches[0][1]
    if keyword_matches:
        keyword_matches.sort(reverse=True)
        return keyword_matches[0][1]
    return None


def get_profile(profile_id: str) -> dict[str, Any] | None:
    profiles = (_profiles_config().get("profiles") or {})
    profile = profiles.get(profile_id)
    return dict(profile) if isinstance(profile, dict) else None


def apply_extraction_profile(
    plan: dict[str, Any],
    requirement: str,
    hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge matched or explicit extraction profile into crawl plan."""
    hints = hints or {}
    profile_id = plan.get("extraction_profile") or hints.get("extraction_profile")

    if not profile_id:
        profile_id = match_extraction_profile(
            requirement,
            plan.get("urls") or ([hints["url"]] if hints.get("url") else []),
            hints,
        )

    if not profile_id:
        plan.setdefault("extraction_strategy", plan.get("extract_mode", "full_text"))
        return plan

    profile = get_profile(profile_id)
    if not profile:
        return plan

    defaults = profile.get("defaults") or {}
    for key, value in defaults.items():
        if key not in plan or plan[key] in (None, {}, []):
            plan[key] = value

    # Profile defaults win for engine/strategy when they target a specific extraction mode.
    if defaults.get("crawler_engine"):
        plan["crawler_engine"] = defaults["crawler_engine"]
    if defaults.get("extraction_strategy"):
        plan["extraction_strategy"] = defaults["extraction_strategy"]

    plan["extraction_profile"] = profile_id
    plan.setdefault("extraction_strategy", defaults.get("extraction_strategy", "dom_selectors"))

    if profile.get("network_capture") and not plan.get("network_capture"):
        plan["network_capture"] = profile["network_capture"]
    if profile.get("json_rules") and not plan.get("json_rules"):
        plan["json_rules"] = profile["json_rules"]

    if defaults.get("use_proxy") and hints.get("use_proxy") is None:
        plan["use_proxy"] = True

    return plan


def infer_extraction_strategy(plan: dict[str, Any]) -> str:
    return str(plan.get("extraction_strategy") or plan.get("extract_mode") or "full_text")
