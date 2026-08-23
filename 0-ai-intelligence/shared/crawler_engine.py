"""Crawler engine selection — shared between planner, orchestrator, and worker."""

from __future__ import annotations

from typing import Any

VALID_ENGINES = frozenset({"fallback", "crawlee", "crawlee_playwright", "auto"})
DEFAULT_ENGINE = "crawlee"

# Alias used in some UI copy
ENGINE_LABELS = {
    "fallback": "HTTP fallback (fast, static pages)",
    "crawlee": "Crawlee + BeautifulSoup (structured crawl)",
    "crawlee_playwright": "Crawlee + Playwright (JavaScript sites)",
    "auto": "Auto (Brain picks from requirement)",
}


def normalize_crawler_engine(source: dict[str, Any] | None, hints: dict[str, Any] | None = None) -> str:
    """Resolve explicit crawler_engine / legacy crawler_type to a canonical engine id."""
    source = source or {}
    hints = hints or {}

    raw = source.get("crawler_engine") or hints.get("crawler_engine")
    if raw and raw != "auto":
        engine = str(raw).strip().lower()
        if engine == "crawlee_beautifulsoup":
            engine = "crawlee"
        if engine in VALID_ENGINES - {"auto"}:
            return engine

    legacy = source.get("crawler_type") or hints.get("crawler_type")
    if legacy == "playwright":
        return "crawlee_playwright"
    if legacy == "beautifulsoup":
        return "crawlee"

    return DEFAULT_ENGINE


def infer_engine_from_requirement(requirement: str, hints: dict[str, Any] | None = None) -> str:
    """Rule-based engine pick when mode is auto."""
    hints = hints or {}
    strategy = hints.get("extraction_strategy") or hints.get("extract_mode")
    if strategy == "network_api":
        return "crawlee_playwright"

    req = requirement.lower()
    js_markers = (
        "javascript",
        "js ",
        " js",
        "react",
        "vue",
        "angular",
        "spa",
        "dynamic",
        "rendered",
        "client-side",
        "single page",
    )
    if any(k in req for k in js_markers):
        return "crawlee_playwright"
    static_markers = ("static", "simple html", "plain html", "http only")
    if any(k in req for k in static_markers):
        return "fallback"
    return DEFAULT_ENGINE


def enforce_for_subscription(engine: str, allowed_scrapers: list[str] | None) -> str:
    """Downgrade engine to what the tenant plan allows."""
    allowed = set(allowed_scrapers or ["crawlee", "rest"])
    if engine == "crawlee_playwright" and "crawlee_playwright" not in allowed:
        if "crawlee" in allowed:
            return "crawlee"
        return "fallback"
    if engine == "crawlee" and "crawlee" not in allowed:
        return "fallback"
    return engine


def sync_legacy_fields(plan: dict[str, Any]) -> None:
    """Keep crawler_type in sync for older worker code paths."""
    engine = plan.get("crawler_engine", DEFAULT_ENGINE)
    plan["crawler_type"] = "playwright" if engine == "crawlee_playwright" else "beautifulsoup"


def apply_engine_to_plan(
    plan: dict[str, Any],
    requirement: str,
    hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set crawler_engine on a plan with auto-detect + subscription enforcement."""
    hints = hints or {}
    mode = hints.get("crawler_engine") or plan.get("crawler_engine") or "auto"
    if mode == "auto":
        engine = infer_engine_from_requirement(requirement, hints)
    else:
        engine = normalize_crawler_engine(plan, hints)

    allowed = hints.get("allowed_scrapers")
    if allowed is None and hints.get("plan_features"):
        allowed = hints["plan_features"].get("scrapers")
    if allowed:
        engine = enforce_for_subscription(engine, allowed)

    plan["crawler_engine"] = engine
    sync_legacy_fields(plan)
    return plan
