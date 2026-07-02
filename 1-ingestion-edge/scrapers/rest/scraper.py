"""REST API scraper - polls HTTP endpoints on interval."""

import logging
import time
from pathlib import Path

import httpx
import yaml

from shared.job_queue import merge_sources, poll_dynamic_jobs
from shared.kafka_client import build_raw_event, create_producer, publish_event

logger = logging.getLogger(__name__)


def load_config() -> list[dict]:
    config_path = Path(__file__).parent.parent / "config" / "rest.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return [s for s in data.get("sources", []) if s.get("enabled", True)]


def scrape_source(client: httpx.Client, source: dict) -> dict | None:
    try:
        resp = client.get(source["url"], timeout=30)
        resp.raise_for_status()
        try:
            payload = resp.json()
        except Exception:
            payload = {"text": resp.text[:5000]}
        return build_raw_event(
            source_id=source["id"],
            source_type="rest",
            vertical=source.get("vertical", "unknown"),
            event_type=source.get("event_type", "rest_response"),
            payload=payload,
            url=source["url"],
            value_score=source.get("value_score"),
        )
    except Exception as e:
        logger.error("REST scrape failed for %s: %s", source["id"], e)
        return None


def run_loop() -> None:
    logging.basicConfig(level=logging.INFO)
    producer = create_producer()
    last_run: dict[str, float] = {}

    with httpx.Client() as client:
        while True:
            static = load_config()
            dynamic = poll_dynamic_jobs(timeout=1)
            sources = merge_sources(static, dynamic)

            now = time.time()
            for source in sources:
                interval = source.get("interval_seconds", 60)
                if now - last_run.get(source["id"], 0) < interval:
                    continue
                event = scrape_source(client, source)
                if event:
                    publish_event(producer, event, topic=source.get("kafka_topic"))
                    logger.info("Published REST event from %s", source["id"])
                last_run[source["id"]] = now

            time.sleep(1)


if __name__ == "__main__":
    run_loop()
