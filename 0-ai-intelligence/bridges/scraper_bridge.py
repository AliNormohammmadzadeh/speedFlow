"""AI-to-Scraper Bridge with tenant isolation and Crawlee job queue."""

import json
import logging
import os
import uuid

import redis

logger = logging.getLogger(__name__)

SCRAPER_QUEUE = os.environ.get("SCRAPER_BRIDGE_QUEUE", "scraper:jobs")
CRAWLEE_QUEUE = os.environ.get("CRAWLEE_QUEUE", "crawlee:jobs")


class ScraperBridge:
    def __init__(self):
        self.redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

    def _tenant_queue(self, base: str, tenant_id: str | None) -> str:
        if tenant_id and tenant_id != "platform":
            return f"{base}:{tenant_id}"
        return base

    def push_crawl_job(self, plan: dict, tenant_id: str | None = None) -> dict:
        """Push a full AI-planned Crawlee job to the worker queue."""
        tid = tenant_id or plan.get("tenant_id", "platform")
        job_id = plan.get("job_id") or str(uuid.uuid4())[:12]
        job = {
            **plan,
            "job_id": job_id,
            "tenant_id": tid,
            "source_id": plan.get("source_id", job_id),
            "type": "crawlee",
        }
        queue = self._tenant_queue(CRAWLEE_QUEUE, tid)
        self.redis.rpush(queue, json.dumps(job))
        self.redis.sadd("crawlee:tenant_queues", queue)
        self.redis.hset(f"crawlee:job:{job_id}", mapping={
            "status": "queued",
            "tenant_id": tid,
            "requirement": plan.get("requirement", "")[:500],
            "pages_crawled": "0",
            "progress_pct": "0",
        })
        logger.info("Queued Crawlee job %s for tenant %s -> %s", job_id, tid, queue)
        return {"job_id": job_id, "queue": queue, "tenant_id": tid}

    def push_targets(self, targets: list[dict], tenant_id: str | None = None) -> int:
        count = 0
        for target in targets:
            if target.get("type") == "crawlee" or target.get("crawler_type"):
                self.push_crawl_job(target, tenant_id=tenant_id)
                count += 1
                continue
            job = {
                "source_id": target.get("source_id") or target.get("id"),
                "type": target.get("type", "rest"),
                "url": target["url"],
                "vertical": target.get("vertical", "unknown"),
                "event_type": target.get("event_type", "ai_discovered"),
                "interval_seconds": target.get("interval_seconds", 60),
                "value_score": target.get("value_score"),
                "tenant_id": tenant_id or target.get("tenant_id", "platform"),
            }
            queue = self._tenant_queue(SCRAPER_QUEUE, tenant_id)
            self.redis.rpush(queue, json.dumps(job))
            count += 1
            logger.info("Pushed scraper job: %s -> %s", job["source_id"], job["url"])
        return count

    def queue_length(self, tenant_id: str | None = None) -> int:
        crawlee_q = self._tenant_queue(CRAWLEE_QUEUE, tenant_id)
        scraper_q = self._tenant_queue(SCRAPER_QUEUE, tenant_id)
        return self.redis.llen(crawlee_q) + self.redis.llen(scraper_q)

    def job_status(self, job_id: str) -> dict:
        data = self.redis.hgetall(f"crawlee:job:{job_id}")
        if not data:
            return {"job_id": job_id, "status": "unknown"}
        parsed = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }
        if "pages_crawled" in parsed:
            parsed["pages_crawled"] = int(parsed["pages_crawled"])
        if "progress_pct" in parsed:
            parsed["progress_pct"] = int(parsed["progress_pct"])
        return parsed | {"job_id": job_id}
