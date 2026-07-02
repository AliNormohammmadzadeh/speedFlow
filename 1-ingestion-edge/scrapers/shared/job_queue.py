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


def _queue_keys(client: redis.Redis) -> list[str]:
    """Global queue plus any per-tenant queues (scraper:jobs:{tenant_id})."""
    keys = [QUEUE_KEY]
    try:
        for key in client.scan_iter(f"{QUEUE_KEY}:*"):
            k = key.decode() if isinstance(key, bytes) else key
            if k != QUEUE_KEY:
                keys.append(k)
    except Exception as exc:
        logger.warning("tenant queue scan failed: %s", exc)
    return keys


def poll_dynamic_jobs(timeout: int = 5) -> list[dict]:
    """Non-blocking poll for new AI-directed scraping targets across all queues."""
    client = get_redis()
    jobs = []
    for _ in range(10):
        keys = _queue_keys(client)
        try:
            item = client.blpop(keys, timeout=timeout)
        except redis.exceptions.TimeoutError:
            # redis-py raises on the blocking timeout instead of returning None
            break
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
            # Propagate per-tenant routing so AI-directed jobs land on the right
            # (possibly dedicated) topic.
            "kafka_topic": job.get("kafka_topic"),
            "tenant_id": job.get("tenant_id"),
            "ai_directed": True,
        }
    return list(merged.values())
