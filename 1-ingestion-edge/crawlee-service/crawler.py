"""Run Crawlee crawlers with proxy rotation, session pool, and AI-driven config."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlparse

import yaml

logger = logging.getLogger(__name__)

_AI_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "0-ai-intelligence"))
if _AI_ROOT not in sys.path:
    sys.path.insert(0, _AI_ROOT)

from extraction.engine import (
    capture_satisfied,
    finalize_page_payload,
    is_bot_block,
    network_capture_config,
    playwright_crawler_extras,
    should_capture_url,
    wait_config_for_url,
)

DEFAULT_ENGINE = "crawlee"


def normalize_crawler_engine(source: dict | None, hints: dict | None = None) -> str:
    source = source or {}
    raw = source.get("crawler_engine")
    if raw in ("fallback", "crawlee", "crawlee_playwright"):
        return raw
    if source.get("crawler_type") == "playwright":
        return "crawlee_playwright"
    return DEFAULT_ENGINE


try:
    import importlib.util

    _engine_path = os.path.join(_AI_ROOT, "shared", "crawler_engine.py")
    _spec = importlib.util.spec_from_file_location("ai_crawler_engine", _engine_path)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        DEFAULT_ENGINE = _mod.DEFAULT_ENGINE
        normalize_crawler_engine = _mod.normalize_crawler_engine
except Exception:
    pass


def _import_pypi_crawlee():
    """Import the PyPI ``crawlee`` package (not ``1-ingestion-edge/scrapers/crawlee``)."""
    shadow_paths = [
        p for p in sys.path
        if p.endswith(f"{os.sep}scrapers") or p.endswith("/scrapers")
    ]
    saved = list(sys.path)
    try:
        for p in shadow_paths:
            while p in sys.path:
                sys.path.remove(p)
        from crawlee import ConcurrencySettings
        from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
        from crawlee.proxy_configuration import ProxyConfiguration
        from crawlee.storages import RequestQueue
        return ConcurrencySettings, BeautifulSoupCrawler, BeautifulSoupCrawlingContext, ProxyConfiguration, RequestQueue
    finally:
        sys.path[:] = saved


try:
    (
        ConcurrencySettings,
        BeautifulSoupCrawler,
        BeautifulSoupCrawlingContext,
        ProxyConfiguration,
        RequestQueue,
    ) = _import_pypi_crawlee()
    CRAWLEE_AVAILABLE = True
except ImportError:
    CRAWLEE_AVAILABLE = False
    logger.warning("Crawlee not installed — fallback HTTP crawler will be used")

_saved_paths = list(sys.path)
try:
    shadow_paths = [p for p in sys.path if p.endswith(f"{os.sep}scrapers") or p.endswith("/scrapers")]
    for p in shadow_paths:
        while p in sys.path:
            sys.path.remove(p)
    from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
finally:
    sys.path[:] = _saved_paths


def playwright_browser_ready() -> bool:
    """True when Playwright Python package and Chromium binary are available."""
    if not PLAYWRIGHT_AVAILABLE:
        return False
    if os.environ.get("SPEEDFLOW_SKIP_PLAYWRIGHT_CHECK") == "1":
        return True
    cache = Path.home() / ".cache" / "ms-playwright"
    if any(cache.glob("chromium-*")):
        return True
    # Docker / CI may install browsers outside the default cache path.
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as exc:
        logger.warning("Playwright browser not ready: %s", exc)
        return False


def crawler_capabilities() -> dict[str, bool]:
    return {
        "crawlee": CRAWLEE_AVAILABLE,
        "crawlee_playwright": PLAYWRIGHT_AVAILABLE and playwright_browser_ready(),
        "fallback": True,
    }


def resolve_proxy_url() -> str | None:
    """Resolve proxy URL from CRAWLEE_PROXY_URL or Novada-style env parts."""
    direct = os.environ.get("CRAWLEE_PROXY_URL", "").strip()
    if direct:
        return direct
    host = os.environ.get("NOVADA_PROXY_HOST", "").strip()
    port = os.environ.get("NOVADA_PROXY_PORT", "").strip()
    user = os.environ.get("NOVADA_PROXY_USER", "").strip()
    password = os.environ.get("NOVADA_PROXY_PASSWORD", "").strip()
    if host and port and user and password:
        return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    return None


_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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
    env_proxy = resolve_proxy_url()
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
    Returns job statistics including requested and actual engine.
    """
    requested = normalize_crawler_engine(job)
    caps = crawler_capabilities()

    async def _finish(stats: dict[str, Any], actual: str) -> dict[str, Any]:
        actual_key = {
            "playwright": "crawlee_playwright",
            "crawlee": "crawlee",
            "fallback": "fallback",
        }.get(actual, actual)
        stats["engine_requested"] = requested
        stats["engine"] = actual
        if requested != actual_key:
            stats["engine_fallback_reason"] = (
                f"Requested {requested} but runtime used {actual_key}"
            )
        return stats

    if requested == "fallback":
        stats = await _run_fallback_job(job, on_result, on_progress)
        return await _finish(stats, "fallback")

    if requested == "crawlee_playwright":
        if caps["crawlee_playwright"]:
            stats = await _run_playwright_job(job, on_result, on_progress)
            return await _finish(stats, "playwright")
        logger.warning(
            "Job %s requested crawlee_playwright but browser unavailable — falling back",
            job.get("job_id"),
        )
        if caps["crawlee"]:
            stats = await _run_beautifulsoup_job(job, on_result, on_progress)
            return await _finish(stats, "crawlee")
        stats = await _run_fallback_job(job, on_result, on_progress)
        return await _finish(stats, "fallback")

    # crawlee (BeautifulSoup) — default
    if caps["crawlee"]:
        stats = await _run_beautifulsoup_job(job, on_result, on_progress)
        return await _finish(stats, "crawlee")

    stats = await _run_fallback_job(job, on_result, on_progress)
    return await _finish(stats, "fallback")


async def _run_beautifulsoup_job(
    job: dict,
    on_result: Callable[[dict], None],
    on_progress: Callable[[int, str | None], None] | None = None,
) -> dict[str, Any]:
    """Crawlee BeautifulSoup crawler for static/structured sites."""
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

    # Isolate each job in its own RequestQueue so re-scraping the same URL in a
    # later job is not silently deduped against a previous run (the worker uses a
    # single long-lived process, so the default queue would persist across jobs).
    request_queue = await RequestQueue.open(name=f"job-{job.get('job_id', uuid.uuid4().hex)}-{uuid.uuid4().hex[:8]}")
    crawler_kwargs["request_manager"] = request_queue

    crawler = BeautifulSoupCrawler(**crawler_kwargs)
    start_urls = list(seed_urls)

    @crawler.router.default_handler
    async def handler(context: BeautifulSoupCrawlingContext) -> None:
        nonlocal results_count
        soup = context.soup
        url = context.request.url

        if job.get("extract_mode") == "full_text":
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            text = soup.get_text(separator=" ", strip=True)
            payload = finalize_page_payload(job, url, title=title, text=text)
        elif selectors:
            dom_fields = _extract_with_selectors(soup, selectors)
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            payload = finalize_page_payload(job, url, title=title, text="", dom_fields=dom_fields)
        else:
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            headings = [h.get_text(strip=True) for h in soup.select("h1,h2,h3")[:20]]
            payload = finalize_page_payload(
                job, url, title=title, text=" ".join(headings), dom_fields={"headings": headings},
            )

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

    try:
        await crawler.run(start_urls)
    finally:
        await request_queue.drop()
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
    api_responses: list[tuple[str, str]] = []
    net_cfg = network_capture_config(job)
    capture_enabled = bool(net_cfg) or job.get("extraction_strategy") == "network_api"
    crawler_kwargs: dict[str, Any] = {
        "max_requests_per_crawl": max_requests,
        "headless": True,
        "browser_new_context_options": {
            "user_agent": _CHROME_UA,
            "viewport": {"width": 1440, "height": 900},
            "locale": "en-US",
        },
        "goto_options": {"wait_until": "domcontentloaded"},
    }
    if proxy_configuration:
        crawler_kwargs["proxy_configuration"] = proxy_configuration
    crawler_kwargs.update(playwright_crawler_extras(job))

    request_queue = await RequestQueue.open(name=f"job-{job.get('job_id', uuid.uuid4().hex)}-{uuid.uuid4().hex[:8]}")
    crawler_kwargs["request_manager"] = request_queue

    crawler = PlaywrightCrawler(**crawler_kwargs)

    @crawler.pre_navigation_hook
    async def capture_api_responses(ctx: PlaywrightCrawlingContext) -> None:
        if not capture_enabled:
            return
        page = ctx.page
        cfg = net_cfg or {"url_include": ["/api/"]}

        async def on_response(response) -> None:
            req_url = response.url
            if not should_capture_url(req_url, cfg):
                return
            try:
                body = await response.text()
            except Exception:
                return
            api_responses.append((req_url, body))

        page.on("response", on_response)

    @crawler.router.default_handler
    async def handler(context: PlaywrightCrawlingContext) -> None:
        nonlocal results_count
        page = context.page
        url = context.request.url
        wait_cfg = wait_config_for_url(url, job) if capture_enabled else {"wait_ms": 3000, "retries": 1, "min_body_chars": 200}
        max_attempts = wait_cfg.get("retries", 1)
        title = ""
        body = ""

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                api_responses.clear()
                await page.reload(wait_until="domcontentloaded")
            await page.wait_for_timeout(wait_cfg.get("wait_ms", 3000))
            title = await page.title()
            body = await page.inner_text("body")
            if is_bot_block(title, body):
                logger.warning(
                    "Playwright attempt %s/%s bot-block for %s (title=%r)",
                    attempt, max_attempts, url, title[:80],
                )
                continue
            if capture_enabled and wait_cfg.get("wait_for_contains"):
                if capture_satisfied(url, api_responses, wait_cfg):
                    break
            elif len(body.strip()) >= wait_cfg.get("min_body_chars", 200):
                break

        dom_fields = None
        if selectors:
            dom_fields = {}
            for key, css in selectors.items():
                els = await page.query_selector_all(css)
                dom_fields[key] = [await el.inner_text() for el in els[:30]]

        payload = finalize_page_payload(
            job, url, title=title, text=body, dom_fields=dom_fields, api_responses=api_responses,
        )

        extracted = payload.get("extracted") or {}
        if job.get("extraction_strategy") == "network_api":
            if extracted.get("stats", {}).get("records_count", 0) == 0 and is_bot_block(title, body):
                raise RuntimeError(
                    "Network API extraction got no records — site may be blocked; rotate proxy or retry"
                )

        on_result({"url": url, "payload": payload, "content_type": "text/html"})
        results_count += 1
        if on_progress:
            on_progress(results_count, None)

    try:
        await crawler.run(seed_urls)
    finally:
        await request_queue.drop()
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
    proxy = resolve_proxy_url()
    client_kwargs: dict = {"timeout": 30, "follow_redirects": True}
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        for url in urls[: int(job.get("max_pages", 10))]:
            try:
                resp = await client.get(url, headers={"User-Agent": "SpeedFlow-Crawlee/1.0"})
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                title = soup.title.string if soup.title else ""
                if selectors:
                    dom_fields = _extract_with_selectors(soup, selectors)
                    payload = finalize_page_payload(job, url, title=title, text="", dom_fields=dom_fields)
                else:
                    text = soup.get_text(separator=" ", strip=True)
                    payload = finalize_page_payload(job, url, title=title, text=text)
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

    proxy = resolve_proxy_url() if job.get("use_proxy") else None
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
