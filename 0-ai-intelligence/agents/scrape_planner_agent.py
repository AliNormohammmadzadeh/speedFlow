"""AI Scrape Planner — converts user requirements into Crawlee job parameters."""

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

from shared.utils import AgentState, llm_complete

logger = logging.getLogger(__name__)

SCRAPE_PLANNER_SYSTEM = """You are a web scraping architect for SpeedFlow platform.
Given a user's data requirement, output ONLY valid JSON with these fields:
{
  "crawler_type": "beautifulsoup" | "playwright",
  "urls": ["https://..."],
  "selectors": {"field_name": "css_selector"},
  "link_selector": "css for pagination/links or null",
  "max_pages": 10-500,
  "max_depth": 0-3,
  "max_concurrency": 1-20,
  "use_proxy": true/false,
  "proxy_tier": "standard" | "premium",
  "use_session_pool": true,
  "same_domain_only": true,
  "extract_mode": "selectors" | "full_text",
  "document_urls": [],
  "event_type": "descriptive_snake_case",
  "vertical": "gaming_esports|financial_markets|accommodation_travel|general",
  "interval_seconds": 300,
  "rate_limit_per_second": 2
}
Choose playwright for JS-heavy SPAs. Use proxy for anti-bot sites. Be conservative with max_pages."""


class ScrapePlannerAgent:
    name = "scrape_planner"

    async def plan_from_requirement(
        self,
        requirement: str,
        tenant_id: str | None = None,
        hints: dict | None = None,
    ) -> dict[str, Any]:
        """Translate natural language user requirement into executable crawl config."""
        hints = hints or {}
        llm_prompt = f"""
User requirement: {requirement}
Tenant: {tenant_id or 'platform'}
Optional hints: {json.dumps(hints)}
Seed URL if any: {hints.get('url', 'none')}
"""
        llm_response = await llm_complete(llm_prompt, system=SCRAPE_PLANNER_SYSTEM)
        plan = self._parse_plan(llm_response, requirement, hints)
        plan["tenant_id"] = tenant_id
        plan["requirement"] = requirement
        plan["source_id"] = plan.get("source_id") or self._slugify(requirement[:40])
        plan["type"] = "crawlee"
        logger.info("Scrape plan for tenant=%s: urls=%s proxy=%s", tenant_id, plan.get("urls"), plan.get("use_proxy"))
        return plan

    def _parse_plan(self, llm_response: str, requirement: str, hints: dict) -> dict:
        # Try JSON extraction from LLM output
        json_match = re.search(r"\{[\s\S]*\}", llm_response)
        if json_match:
            try:
                plan = json.loads(json_match.group())
                return self._normalize_plan(plan, requirement, hints)
            except json.JSONDecodeError:
                pass
        return self._rule_based_plan(requirement, hints)

    def _normalize_plan(self, plan: dict, requirement: str, hints: dict) -> dict:
        urls = plan.get("urls") or []
        if hints.get("url"):
            urls = [hints["url"]] + [u for u in urls if u != hints["url"]]
        if not urls:
            urls = self._extract_urls_from_text(requirement)

        plan.setdefault("crawler_type", "beautifulsoup")
        plan.setdefault("max_pages", min(int(hints.get("max_pages", 50)), 500))
        plan.setdefault("max_depth", 1)
        plan.setdefault("max_concurrency", 5)
        plan.setdefault("use_proxy", self._needs_proxy(requirement))
        plan.setdefault("proxy_tier", "premium" if plan["use_proxy"] else "standard")
        plan.setdefault("use_session_pool", True)
        plan.setdefault("same_domain_only", True)
        plan.setdefault("extract_mode", "selectors" if plan.get("selectors") else "full_text")
        plan.setdefault("selectors", plan.get("selectors") or {})
        plan.setdefault("event_type", "user_scrape")
        plan.setdefault("vertical", hints.get("vertical", "general"))
        plan["urls"] = urls
        return plan

    def _rule_based_plan(self, requirement: str, hints: dict) -> dict:
        req_lower = requirement.lower()
        urls = self._extract_urls_from_text(requirement)
        if hints.get("url"):
            urls = [hints["url"]]

        use_playwright = any(k in req_lower for k in ["javascript", "react", "spa", "dynamic", "rendered"])
        use_proxy = self._needs_proxy(requirement)
        extract_full = any(k in req_lower for k in ["document", "article", "full text", "pdf"])

        selectors = {}
        if "price" in req_lower:
            selectors["price"] = ".price, [class*='price'], [data-price]"
        if "title" in req_lower:
            selectors["title"] = "h1, .title, [class*='title']"

        return {
            "crawler_type": "playwright" if use_playwright else "beautifulsoup",
            "urls": urls or ["https://httpbin.org/html"],
            "selectors": selectors,
            "link_selector": "a[href]" if any(k in req_lower for k in ["crawl", "all pages", "follow links"]) else None,
            "max_pages": int(hints.get("max_pages", 30)),
            "max_depth": 2 if "deep" in req_lower else 1,
            "max_concurrency": 10 if "fast" in req_lower else 5,
            "use_proxy": use_proxy,
            "proxy_tier": "premium" if use_proxy else "standard",
            "use_session_pool": True,
            "same_domain_only": True,
            "extract_mode": "full_text" if extract_full else "selectors",
            "document_urls": [u for u in urls if u.lower().endswith(".pdf")],
            "event_type": "user_scrape",
            "vertical": hints.get("vertical", "general"),
        }

    def _needs_proxy(self, text: str) -> bool:
        keywords = ["blocked", "cloudflare", "anti-bot", "many requests", "scale", "rate limit", "proxy"]
        return any(k in text.lower() for k in keywords)

    def _extract_urls_from_text(self, text: str) -> list[str]:
        return re.findall(r"https?://[^\s\)\]\"']+", text)

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug[:48] or "scrape-job"
