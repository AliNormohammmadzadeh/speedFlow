"""Unit tests for crawler engine selection."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "0-ai-intelligence"))

from shared.crawler_engine import (  # noqa: E402
    apply_engine_to_plan,
    enforce_for_subscription,
    infer_engine_from_requirement,
    normalize_crawler_engine,
)


def test_normalize_explicit_engine():
    assert normalize_crawler_engine({"crawler_engine": "fallback"}) == "fallback"
    assert normalize_crawler_engine({"crawler_engine": "crawlee_playwright"}) == "crawlee_playwright"
    assert normalize_crawler_engine({"crawler_type": "playwright"}) == "crawlee_playwright"


def test_infer_playwright_for_spa():
    assert infer_engine_from_requirement("Scrape a React SPA product catalog") == "crawlee_playwright"


def test_infer_crawlee_default():
    assert infer_engine_from_requirement("Scrape titles from example.com") == "crawlee"


def test_starter_plan_downgrades_playwright():
    allowed = ["rest", "crawlee"]
    assert enforce_for_subscription("crawlee_playwright", allowed) == "crawlee"


def test_apply_auto_with_hint_override():
    plan = apply_engine_to_plan(
        {},
        "Scrape example.com titles",
        hints={"crawler_engine": "fallback", "allowed_scrapers": ["rest", "crawlee"]},
    )
    assert plan["crawler_engine"] == "fallback"
    assert plan["crawler_type"] == "beautifulsoup"


def test_apply_auto_detects_js():
    plan = apply_engine_to_plan(
        {},
        "Scrape dynamic JavaScript dashboard",
        hints={"crawler_engine": "auto", "allowed_scrapers": ["rest", "crawlee", "crawlee_playwright"]},
    )
    assert plan["crawler_engine"] == "crawlee_playwright"
    assert plan["crawler_type"] == "playwright"


if __name__ == "__main__":
    for fn in (
        test_normalize_explicit_engine,
        test_infer_playwright_for_spa,
        test_infer_crawlee_default,
        test_starter_plan_downgrades_playwright,
        test_apply_auto_with_hint_override,
        test_apply_auto_detects_js,
    ):
        fn()
        print(f"OK {fn.__name__}")
