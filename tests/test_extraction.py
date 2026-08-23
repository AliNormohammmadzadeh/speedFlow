#!/usr/bin/env python3
"""Unit tests for declarative extraction profiles and runtime engine."""

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "0-ai-intelligence"))
sys.path.insert(0, os.path.join(ROOT, "1-ingestion-edge", "crawlee-service"))

os.environ["CONFIG_PATH"] = os.path.join(ROOT, "config")

from shared.extraction import apply_extraction_profile, match_extraction_profile  # noqa: E402
from extraction.engine import (  # noqa: E402
    apply_json_rules,
    dom_fields_to_records,
    finalize_page_payload,
)


SAMPLE_MARKETS = {
    "ok": True,
    "data": [
        {
            "name": "Match Winner",
            "selections": [
                {"name": "Team A", "odds": 2.1, "type": "home"},
                {"name": "Team B", "odds": 1.7, "type": "away"},
            ],
        }
    ],
}


class ExtractionProfileTests(unittest.TestCase):
    def test_match_quotes_host(self):
        pid = match_extraction_profile(
            "Extract quotes and authors",
            urls=["https://quotes.toscrape.com/"],
        )
        self.assertEqual(pid, "quotes_listing")

    def test_match_hn_host(self):
        pid = match_extraction_profile(
            "Get story titles and scores",
            urls=["https://news.ycombinator.com/"],
        )
        self.assertEqual(pid, "news_listing")

    def test_match_betting_keywords(self):
        pid = match_extraction_profile(
            "Scrape betting odds and markets from match page",
            urls=["https://example-betting.io/match/123"],
        )
        self.assertEqual(pid, "spa_network_api")

    def test_apply_profile_merges_selectors(self):
        plan = {"urls": ["https://quotes.toscrape.com/"]}
        apply_extraction_profile(plan, "Extract all quotes and authors")
        self.assertEqual(plan["extraction_profile"], "quotes_listing")
        self.assertIn("quote", plan.get("selectors", {}))
        self.assertEqual(plan["extraction_strategy"], "dom_selectors")


class ExtractionEngineTests(unittest.TestCase):
    def test_dom_fields_to_records(self):
        rows = dom_fields_to_records({"quote": ["a", "b"], "author": ["x", "y"]})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["quote"], "a")

    def test_json_rules_markets(self):
        rules = [
            {
                "id": "market_selections",
                "url_match": "*/api/markets/*",
                "records_path": "data",
                "map": {"market": "name"},
                "expand": {
                    "array": "selections",
                    "fields": {"selection": "name", "odds": "odds", "side": "type"},
                },
            }
        ]
        records, entities = apply_json_rules(
            rules,
            [("https://site.io/api/markets/1", json.dumps(SAMPLE_MARKETS))],
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["market"], "Match Winner")
        self.assertNotIn("entities", entities or {})

    def test_finalize_payload_shape(self):
        job = {
            "extraction_strategy": "dom_selectors",
            "extraction_profile": "quotes_listing",
        }
        payload = finalize_page_payload(
            job,
            "https://quotes.toscrape.com/",
            title="Quotes",
            text="",
            dom_fields={"quote": ["Life is short"], "author": ["Steve"]},
        )
        self.assertIn("extracted", payload)
        self.assertEqual(payload["extracted"]["strategy"], "dom_selectors")
        self.assertEqual(len(payload["extracted"]["records"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
