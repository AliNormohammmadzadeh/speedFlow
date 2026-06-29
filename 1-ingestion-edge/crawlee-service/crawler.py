"""Run Crawlee crawlers with proxy rotation, session pool, and AI-driven config."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import yaml

logger = logging.getLogger(__name__)

try:
    from crawlee import ConcurrencySettings
    from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
    from crawlee.proxy_configuration import ProxyConfiguration
    CRAWLEE_AVAILABLE = True
except ImportError:
    CRAWLEE_AVAILABLE = False
    logger.warning("Crawlee not installed — fallback HTTP crawler will be used")

try:
    from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def load_proxy_config() -> dict:
    path = Path(__file__).parent / "config" / "proxies.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def build_proxy_configuration(job: dict) -> Any | None:
    if not job.get("use_proxy", False):
        return None

    proxy_cfg = load_proxy_config()
    tier = job.get("proxy_tier", "standard")

    tiered = proxy_cfg.get("tiered_proxy_urls", {})
    if tier in tiered and tiered[tier]:
        urls = [u for u in tiered[tier] if u and not str(u).startswith("${")]
        if urls:
            return ProxyConfiguration(tiered_proxy_urls=[urls])

    flat = proxy_cfg.get("proxy_urls", [])
    env_proxy = os.environ.get("CRAWLEE_PROXY_URL")
    if env_proxy:
        flat = flat + [env_proxy]
    flat = [u for u in flat if u and not str(u).startswith("${")]
    if flat:
        return ProxyConfiguration(proxy_urls=flat)

    return None


def _extract_with_selectors(soup, selectors: dict[str, str]) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    for key, css in selectors.items():
        if css.startswith("@"):
            el = soup.select_one(css[1:])
            extracted[key] = el.get(attr) if el and (attr := css.split("@")[-1]) else None
        else:
            els = soup.select(css)
            if len(els) == 1:
                extracted[key] = els[0].get_text(strip=True)
            elif els:
                extracted[key] = [e.get_text(strip=True) for e in els[:50]]
            else:
                extracted[key] = None
    return extracted


async def run_crawlee_job(
    job: dict,
    on_result: Callable[[dict], None],
    on_progress: Callable[[int, str | None], None] | None = None,
) -> dict[str, Any]:
    """
    Execute a crawl job. Calls on_result for each extracted page/document.
    Returns job statistics.
    """
    if job.get("crawler_type") == "playwright" and PLAYWRIGHT_AVAILABLE:
        return await _run_playwright_job(job, on_result, on_progress)

    if not CRAWLEE_AVAILABLE:
        return await _run_fallback_job(job, on_result, on_progress)

    proxy_configuration = build_proxy_configuration(job)
    max_concurrency = int(job.get("max_concurrency", 5))
    max_requests = int(job.get("max_pages", 50))
    selectors = job.get("selectors", {})
    link_selector = job.get("link_selector")
    max_depth = int(job.get("max_depth", 1))
    same_domain = job.get("same_domain_only", True)
    seed_urls = job.get("urls") or ([job["url"]] if job.get("url") else [])
    if not seed_urls:
        raise ValueError("Crawl job requires urls or url")

    results_count = 0
    seen_domains = {urlparse(u).netloc for u in seed_urls}

    desired_concurrency = min(int(job.get("desired_concurrency", max_concurrency)), max_concurrency)
    concurrency = ConcurrencySettings(
        max_concurrency=max_concurrency,
        desired_concurrency=max(1, desired_concurrency),
    )
    crawler_kwargs: dict[str, Any] = {
        "max_requests_per_crawl": max_requests,
        "max_crawl_depth": max_depth,
        "use_session_pool": job.get("use_session_pool", True),
        "retry_on_blocked": True,
        "concurrency_settings": concurrency,
    }
    if proxy_configuration:
        crawler_kwargs["proxy_configuration"] = proxy_configuration

    crawler = BeautifulSoupCrawler(**crawler_kwargs)
    start_urls = list(seed_urls)

    @crawler.router.default_handler
    async def handler(context: BeautifulSoupCrawlingContext) -> None:
        nonlocal results_count
        soup = context.soup
        url = context.request.url

        if job.get("extract_mode") == "full_text":
            payload = {
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "text": soup.get_text(separator=" ", strip=True)[:50000],
                "url": url,
            }
        elif selectors:
            payload = _extract_with_selectors(soup, selectors)
            payload["url"] = url
        else:
            payload = {
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "url": url,
                "headings": [h.get_text(strip=True) for h in soup.select("h1,h2,h3")[:20]],
            }

        if context.proxy_info:
            payload["_proxy"] = context.proxy_info.url

        on_result({
            "url": url,
            "payload": payload,
            "content_type": "text/html",
        })
        results_count += 1
        if on_progress:
            on_progress(results_count, None)

        if link_selector and context.crawler.request_manager:
            depth = context.request.crawl_depth or 0
            if depth < max_depth:
                for link in soup.select(link_selector):
                    href = link.get("href")
                    if not href:
                        continue
                    absolute = urljoin(url, href)
                    if same_domain and urlparse(absolute).netloc not in seen_domains:
                        continue
                    await context.add_requests([absolute])

    await crawler.run(start_urls)
    return {"pages_crawled": results_count, "engine": "crawlee", "proxy": bool(proxy_configuration)}


async def _run_playwright_job(
    job: dict,
    on_result: Callable[[dict], None],
    on_progress: Callable[[int, str | None], None] | None = None,
) -> dict[str, Any]:
    """JS-heavy sites via PlaywrightCrawler."""
    max_requests = int(job.get("max_pages", 50))
    selectors = job.get("selectors", {})
    seed_urls = job.get("urls") or ([job["url"]] if job.get("url") else [])
    results_count = 0

    proxy_configuration = build_proxy_configuration(job)
    crawler_kwargs: dict[str, Any] = {
        "max_requests_per_crawl": max_requests,
        "headless": True,
    }
    if proxy_configuration:
        crawler_kwargs["proxy_configuration"] = proxy_configuration

    crawler = PlaywrightCrawler(**crawler_kwargs)

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        nonlocal results_count
        page = context.page
        url = context.request.url
        title = await page.title()
        if selectors:
            payload = {}
            for key, css in selectors.items():
                els = await page.query_selector_all(css)
                payload[key] = [await el.inner_text() for el in els[:30]]
        else:
            body = await page.inner_text("body")
            payload = {"title": title, "text": body[:50000], "url": url}
        payload["url"] = url
        on_result({"url": url, "payload": payload, "content_type": "text/html"})
        results_count += 1
        if on_progress:
            on_progress(results_count, None)

    await crawler.run(seed_urls)
    return {"pages_crawled": results_count, "engine": "playwright", "proxy": bool(proxy_configuration)}


async def _run_fallback_job(
    job: dict,
    on_result: Callable[[dict], None],
    on_progress: Callable[[int, str | None], None] | None = None,
) -> dict[str, Any]:
    """Lightweight fallback when Crawlee is unavailable."""
    import httpx
    from bs4 import BeautifulSoup

    urls = job.get("urls") or ([job["url"]] if job.get("url") else [])
    selectors = job.get("selectors", {})
    count = 0
    proxy = os.environ.get("CRAWLEE_PROXY_URL")
    client_kwargs: dict = {"timeout": 30, "follow_redirects": True}
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        for url in urls[: int(job.get("max_pages", 10))]:
            try:
                resp = await client.get(url, headers={"User-Agent": "SpeedFlow-Crawlee/1.0"})
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                if selectors:
                    payload = _extract_with_selectors(soup, selectors)
                else:
                    payload = {"title": soup.title.string if soup.title else None}
                payload["url"] = url
                on_result({"url": url, "payload": payload, "content_type": resp.headers.get("content-type", "")})
                count += 1
                if on_progress:
                    on_progress(count, None)
            except Exception as e:
                logger.error("Fallback crawl failed %s: %s", url, e)
                if on_progress:
                    on_progress(count, str(e))
    return {"pages_crawled": count, "engine": "fallback"}


async def fetch_document(url: str, job: dict, on_result: Callable[[dict], None]) -> bool:
    """Fetch PDF or other documents (non-HTML)."""
    import httpx

    proxy = os.environ.get("CRAWLEE_PROXY_URL") if job.get("use_proxy") else None
    async with httpx.AsyncClient(proxy=proxy, timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            on_result({
                "url": url,
                "payload": {"size_bytes": len(resp.content), "content_type": content_type},
                "content_type": content_type,
                "binary": True,
            })
            return True
        if "json" in content_type:
            on_result({
                "url": url,
                "payload": resp.json() if resp.content else {},
                "content_type": content_type,
            })
            return True
    return False
