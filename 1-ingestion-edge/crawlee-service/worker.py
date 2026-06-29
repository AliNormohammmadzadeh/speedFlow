"""Scalable Crawlee worker — consumes tenant-scoped jobs from Redis."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone

import redis

sys.path.insert(0, os.path.dirname(__file__))
from shared.job_status import update_scrape_job
from shared.kafka_client import build_raw_event, create_producer, publish_event

from crawler import fetch_document, run_crawlee_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [crawlee-worker] %(message)s")
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
GLOBAL_QUEUE = os.environ.get("CRAWLEE_QUEUE", "crawlee:jobs")
_running = True


def queue_keys() -> list[str]:
    client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    keys = [GLOBAL_QUEUE]
    for key in client.scan_iter("crawlee:jobs:*"):
        k = key.decode() if isinstance(key, bytes) else key
        if k != GLOBAL_QUEUE:
            keys.append(k)
    return keys


def get_redis() -> redis.Redis:
    return redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


def handle_signal(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def _sync_job_status(client: redis.Redis, job_id: str, **fields) -> None:
    mapping = {k: str(v) for k, v in fields.items() if v is not None}
    if mapping:
        client.hset(f"crawlee:job:{job_id}", mapping=mapping)
        client.expire(f"crawlee:job:{job_id}", 86400 * 7)
    update_scrape_job(job_id, **fields)


def process_job(job: dict, producer) -> dict:
    tenant_id = job.get("tenant_id", "platform")
    job_id = job.get("job_id", job.get("source_id", "unknown"))
    vertical = job.get("vertical") or "unknown"
    event_type = job.get("event_type") or "crawled_content"
    document_urls = [u for u in (job.get("document_urls") or []) if u]
    max_pages = int(job.get("max_pages", 50))
    client = get_redis()

    results: list[dict] = []
    pages_done = 0

    def on_progress(pages: int, error: str | None = None) -> None:
        nonlocal pages_done
        pages_done = pages
        pct = min(100, int((pages / max(max_pages, 1)) * 100))
        _sync_job_status(
            client, job_id,
            status="running",
            pages_crawled=pages,
            progress_pct=pct,
            error_message=error,
        )

    def on_result(item: dict):
        payload = item["payload"]
        if isinstance(payload, dict):
            payload["_content_type"] = item.get("content_type")
            payload["_page_url"] = item.get("url")
        event = build_raw_event(
            source_id=f"{tenant_id}:{job_id}",
            source_type="crawlee",
            vertical=vertical,
            event_type=event_type,
            payload=payload if isinstance(payload, dict) else {"data": payload},
            url=item.get("url"),
            value_score=job.get("value_score"),
        )
        event["tenant_id"] = tenant_id
        event["job_id"] = job_id
        topic = job.get("kafka_topic") or os.environ.get("KAFKA_RAW_TOPIC", "raw_stream")
        publish_event(producer, event, topic=topic)
        results.append(event)
        on_progress(len(results))

    async def execute():
        stats = {"pages_crawled": 0, "documents_fetched": 0}
        for doc_url in document_urls:
            if await fetch_document(doc_url, job, on_result):
                stats["documents_fetched"] += 1
        crawl_stats = await run_crawlee_job(job, on_result, on_progress=on_progress)
        stats.update(crawl_stats)
        return stats

    stats = asyncio.run(execute())
    _sync_job_status(
        client, job_id,
        status="completed",
        pages_crawled=stats.get("pages_crawled", 0),
        progress_pct=100,
        completed_at=datetime.now(timezone.utc),
    )
    logger.info("Job %s done: %s", job_id, stats)
    return stats


def worker_loop():
    client = get_redis()
    producer = create_producer()
    logger.info("Crawlee worker %s started", WORKER_ID)

    while _running:
        keys = queue_keys()
        try:
            item = client.blpop(keys, timeout=5)
        except redis.exceptions.TimeoutError:
            # redis-py raises on the blocking timeout instead of returning None
            continue
        if not item:
            continue
        job = {}
        try:
            _, raw = item
            job = json.loads(raw)
            job_id = job.setdefault("job_id", job.get("source_id", f"job-{WORKER_ID}"))
            _sync_job_status(client, job_id, status="running", progress_pct=0, pages_crawled=0)
            process_job(job, producer)
        except Exception as e:
            logger.exception("Job failed: %s", e)
            job_id = job.get("job_id", "unknown")
            _sync_job_status(
                client, job_id,
                status="failed",
                error_message=str(e)[:500],
                completed_at=datetime.now(timezone.utc),
            )


if __name__ == "__main__":
    worker_loop()
