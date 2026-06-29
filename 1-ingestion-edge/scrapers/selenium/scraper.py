"""Selenium + Playwright scraper for JS-rendered pages."""

import logging
import os
import time
from pathlib import Path

import yaml

from shared.job_queue import merge_sources, poll_dynamic_jobs
from shared.kafka_client import build_raw_event, create_producer, publish_event

logger = logging.getLogger(__name__)

CHROME_BIN = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
CHROMEDRIVER = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")


def load_config() -> list[dict]:
    config_path = Path(__file__).parent.parent / "config" / "selenium.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return [s for s in data.get("sources", []) if s.get("enabled", True)]


def scrape_with_selenium(source: dict) -> dict | None:
    """Render page with headless Chrome via Selenium WebDriver."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.binary_location = CHROME_BIN

        service = Service(executable_path=CHROMEDRIVER)
        driver = webdriver.Chrome(service=service, options=options)
        try:
            driver.set_page_load_timeout(45)
            driver.get(source["url"])
            time.sleep(float(source.get("wait_seconds", 2)))
            title = driver.title
            body_text = driver.find_element("tag name", "body").text[:10000]
            payload = {
                "title": title,
                "text_preview": body_text,
                "html_length": len(driver.page_source),
                "mode": "selenium_chrome",
            }
            selector = source.get("selector")
            if selector:
                elements = driver.find_elements("css selector", selector)
                payload["selected"] = [el.text.strip() for el in elements[:30] if el.text.strip()]
            return build_raw_event(
                source_id=source["id"],
                source_type="selenium",
                vertical=source.get("vertical", "unknown"),
                event_type=source.get("event_type", "rendered_page"),
                payload=payload,
                url=source["url"],
                value_score=source.get("value_score"),
            )
        finally:
            driver.quit()
    except Exception as e:
        logger.error("Selenium scrape failed for %s: %s", source["id"], e)
        return None


def scrape_with_playwright(source: dict) -> dict | None:
    """Render page with Playwright Chromium."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(source["url"], wait_until="networkidle", timeout=45000)
            title = page.title()
            body_text = page.inner_text("body")[:10000]
            payload = {
                "title": title,
                "text_preview": body_text,
                "mode": "playwright_chromium",
            }
            selector = source.get("selector")
            if selector:
                payload["selected"] = page.locator(selector).all_inner_texts()[:30]
            browser.close()
            return build_raw_event(
                source_id=source["id"],
                source_type="selenium",
                vertical=source.get("vertical", "unknown"),
                event_type=source.get("event_type", "rendered_page"),
                payload=payload,
                url=source["url"],
                value_score=source.get("value_score"),
            )
    except Exception as e:
        logger.error("Playwright scrape failed for %s: %s", source["id"], e)
        return None


def scrape_source(source: dict) -> dict | None:
    engine = source.get("engine", os.environ.get("SCRAPER_ENGINE", "selenium"))
    if engine == "playwright":
        return scrape_with_playwright(source)
    return scrape_with_selenium(source)


def run_loop() -> None:
    logging.basicConfig(level=logging.INFO)
    producer = create_producer()
    last_run: dict[str, float] = {}

    while True:
        static = load_config()
        dynamic = poll_dynamic_jobs(timeout=1)
        sources = merge_sources(static, dynamic)
        now = time.time()
        for source in sources:
            interval = source.get("interval_seconds", 600)
            if now - last_run.get(source["id"], 0) < interval:
                continue
            event = scrape_source(source)
            if event:
                publish_event(producer, event)
                logger.info("Published %s event from %s", event.get("source_type"), source["id"])
            last_run[source["id"]] = now
        time.sleep(10)


if __name__ == "__main__":
    run_loop()
