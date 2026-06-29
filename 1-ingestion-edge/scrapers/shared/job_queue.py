"""Consume dynamic scraping jobs pushed by the Discovery Agent bridge."""

import json
import logging
import os
import time

import redis

logger = logging.getLogger(__name__)

QUEUE_KEY = os.environ.get("SCRAPER_BRIDGE_QUEUE", "scraper:jobs")


def get_redis() -> redis.Redis:
    return redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


def poll_dynamic_jobs(timeout: int = 5) -> list[dict]:
    """Non-blocking poll for new AI-directed scraping targets."""
    client = get_redis()
    jobs = []
    for _ in range(10):
        item = client.blpop(QUEUE_KEY, timeout=timeout)
        if not item:
            break
        _, raw = item
        try:
            jobs.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning("Invalid job payload: %s", raw)
    return jobs


def merge_sources(static_sources: list[dict], dynamic_jobs: list[dict]) -> list[dict]:
    """Merge file-based config with AI-pushed targets."""
    merged = {s["id"]: s for s in static_sources}
    for job in dynamic_jobs:
        source_id = job.get("source_id") or job.get("id")
        if not source_id:
            continue
        merged[source_id] = {
            "id": source_id,
            "type": job.get("type", "rest"),
            "vertical": job.get("vertical", "unknown"),
            "url": job["url"],
            "interval_seconds": job.get("interval_seconds", 60),
            "event_type": job.get("event_type", "dynamic_scrape"),
            "enabled": True,
            "value_score": job.get("value_score"),
            "ai_directed": True,
        }
    return list(merged.values())
