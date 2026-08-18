"""Scrape request guardrails — enforce read-only public web/API data collection only.

Used at Platform API (gateway), orchestrator (plan queue), and crawlee worker
(last line of defense). Policy lives in config/security/scrape_guardrails.yaml.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from shared.utils import load_yaml

_URL_RE = re.compile(r"https?://[^\s\)\]\"']+", re.IGNORECASE)
_DISALLOWED_SCHEME_RE = re.compile(r"(?i)\b(?:file|javascript|data|ftp):")


class ScrapeGuardrailViolation(Exception):
    """Raised when a scrape request or crawl plan violates platform policy."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _policy() -> dict[str, Any]:
    return load_yaml("security/scrape_guardrails.yaml") or {}


def _extract_urls(*texts: str | None) -> list[str]:
    found: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in _URL_RE.findall(text):
            if match not in found:
                found.append(match)
    return found


def _validate_requirement_text(requirement: str, policy: dict[str, Any]) -> None:
    limits = policy.get("limits", {})
    min_len = int(limits.get("requirement_min_length", 10))
    max_len = int(limits.get("requirement_max_length", 4000))

    text = (requirement or "").strip()
    if len(text) < min_len:
        raise ScrapeGuardrailViolation(
            "requirement_too_short",
            f"Requirement must be at least {min_len} characters and describe data to collect.",
        )
    if len(text) > max_len:
        raise ScrapeGuardrailViolation(
            "requirement_too_long",
            f"Requirement exceeds maximum length ({max_len} characters).",
        )

    for rule in policy.get("forbidden_intent_patterns", []):
        pattern = rule.get("pattern")
        if pattern and re.search(pattern, text):
            raise ScrapeGuardrailViolation(
                rule.get("code", "forbidden_intent"),
                rule.get("message", "This request is not allowed."),
            )

    if _DISALLOWED_SCHEME_RE.search(text):
        raise ScrapeGuardrailViolation(
            "invalid_url_scheme",
            "Only public http(s) URLs are allowed — file, javascript, data, and ftp are blocked.",
        )

    urls = _extract_urls(text)
    if urls:
        return

    lowered = text.lower()
    keywords = policy.get("scrape_intent_keywords", [])
    if not any(kw in lowered for kw in keywords):
        raise ScrapeGuardrailViolation(
            "not_scrape_intent",
            "Describe read-only data to collect (scrape/crawl/extract) or include a public http(s) URL.",
        )


def _host_blocked(hostname: str, policy: dict[str, Any]) -> bool:
    host = (hostname or "").lower().strip(".")
    if not host:
        return True

    blocked = {h.lower() for h in policy.get("blocked_url_hosts", [])}
    if host in blocked or host.endswith(".localhost"):
        return True

    if policy.get("block_private_ips", True) or policy.get("block_link_local", True):
        try:
            ip = ipaddress.ip_address(host.strip("[]"))
            if policy.get("block_private_ips", True) and ip.is_private:
                return True
            if policy.get("block_link_local", True) and ip.is_link_local:
                return True
            if ip.is_loopback:
                return True
            if ip.is_reserved:
                return True
        except ValueError:
            pass

    return False


def _validate_url(url: str, policy: dict[str, Any]) -> None:
    parsed = urlparse(url.strip())
    allowed_schemes = {s.lower() for s in policy.get("allowed_url_schemes", ["http", "https"])}

    if parsed.scheme.lower() not in allowed_schemes:
        raise ScrapeGuardrailViolation(
            "invalid_url_scheme",
            f"Only public http(s) URLs are allowed (got scheme '{parsed.scheme or 'missing'}').",
        )

    if parsed.username or parsed.password:
        raise ScrapeGuardrailViolation(
            "url_credentials",
            "URLs must not embed credentials.",
        )

    if _host_blocked(parsed.hostname or "", policy):
        raise ScrapeGuardrailViolation(
            "blocked_target",
            f"Target host is not allowed for scraping: {parsed.hostname}",
        )


def _validate_urls(urls: list[str], policy: dict[str, Any]) -> None:
    max_urls = int(policy.get("limits", {}).get("max_urls_per_job", 25))
    if len(urls) > max_urls:
        raise ScrapeGuardrailViolation(
            "too_many_urls",
            f"At most {max_urls} URLs are allowed per scrape job.",
        )
    for url in urls:
        _validate_url(url, policy)


def enforce_scrape_guardrails(
    requirement: str,
    *,
    url: str | None = None,
    max_pages: int | None = None,
) -> None:
    """Validate natural-language scrape request before planning or queueing."""
    policy = _policy()
    _validate_requirement_text(requirement, policy)

    urls = _extract_urls(requirement)
    if url and url not in urls:
        urls.insert(0, url)

    if urls:
        _validate_urls(urls, policy)

    if max_pages is not None and max_pages < 1:
        raise ScrapeGuardrailViolation(
            "invalid_max_pages",
            "max_pages must be at least 1.",
        )


def enforce_crawl_plan_guardrails(plan: dict[str, Any]) -> None:
    """Validate executable crawl plan URLs (after AI planning, before worker run)."""
    policy = _policy()
    requirement = str(plan.get("requirement") or "")
    if requirement:
        _validate_requirement_text(requirement, policy)

    urls: list[str] = []
    for u in plan.get("urls") or []:
        if u and u not in urls:
            urls.append(u)
    if plan.get("url") and plan["url"] not in urls:
        urls.insert(0, plan["url"])
    for u in plan.get("document_urls") or []:
        if u and u not in urls:
            urls.append(u)

    urls.extend(_extract_urls(requirement))
    # Preserve order, dedupe
    seen: set[str] = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    if not unique:
        raise ScrapeGuardrailViolation(
            "no_public_urls",
            "Crawl plan must include at least one public http(s) URL.",
        )

    _validate_urls(unique, policy)
