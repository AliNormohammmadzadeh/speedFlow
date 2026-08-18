"""Tests for scrape request guardrails."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "0-ai-intelligence"))
os.environ.setdefault("CONFIG_PATH", os.path.join(ROOT, "config"))

from shared.scrape_guardrails import (  # noqa: E402
    ScrapeGuardrailViolation,
    enforce_crawl_plan_guardrails,
    enforce_scrape_guardrails,
)


def _assert_raises(code: str, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ScrapeGuardrailViolation as exc:
        assert exc.code == code, f"expected {code}, got {exc.code}: {exc.message}"
    else:
        raise AssertionError(f"expected ScrapeGuardrailViolation({code})")


def test_valid_scrape_with_url():
    enforce_scrape_guardrails(
        "Scrape article titles from https://example.com",
        url="https://example.com",
        max_pages=5,
    )


def test_valid_scrape_intent_without_explicit_url_field():
    enforce_scrape_guardrails("Crawl and extract product prices from public listings on the web")


def test_blocks_hacking_intent():
    _assert_raises(
        "non_scrape_security",
        enforce_scrape_guardrails,
        "Hack into https://example.com and dump credentials",
    )


def test_blocks_non_scrape_action():
    _assert_raises(
        "non_scrape_action",
        enforce_scrape_guardrails,
        "Create account and post comments on https://example.com",
    )


def test_blocks_localhost_target():
    _assert_raises(
        "blocked_target",
        enforce_scrape_guardrails,
        "Scrape titles from http://localhost:8080/admin",
    )


def test_blocks_private_ip():
    _assert_raises(
        "blocked_target",
        enforce_scrape_guardrails,
        "Scrape data from http://192.168.1.50/internal",
    )


def test_blocks_non_scrape_vague_text():
    _assert_raises(
        "not_scrape_intent",
        enforce_scrape_guardrails,
        "Hello world please help me",
    )


def test_crawl_plan_validates_urls():
    enforce_crawl_plan_guardrails(
        {
            "requirement": "Scrape odds from https://example.com/match",
            "urls": ["https://example.com/match"],
            "max_pages": 3,
        }
    )


def test_blocks_file_scheme_in_requirement_text():
    _assert_raises(
        "invalid_url_scheme",
        enforce_scrape_guardrails,
        "Fetch file:///etc/passwd contents please",
    )
    _assert_raises(
        "invalid_url_scheme",
        enforce_crawl_plan_guardrails,
        {"requirement": "Scrape local file contents please", "urls": ["file:///etc/passwd"]},
    )


def main():
    tests = [
        test_valid_scrape_with_url,
        test_valid_scrape_intent_without_explicit_url_field,
        test_blocks_hacking_intent,
        test_blocks_non_scrape_action,
        test_blocks_localhost_target,
        test_blocks_private_ip,
        test_blocks_non_scrape_vague_text,
        test_crawl_plan_validates_urls,
        test_blocks_file_scheme_in_requirement_text,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print()
    if failed:
        print(f"{failed} failed, {len(tests) - failed} passed")
        sys.exit(1)
    print(f"{len(tests)} passed, 0 failed")


if __name__ == "__main__":
    main()
