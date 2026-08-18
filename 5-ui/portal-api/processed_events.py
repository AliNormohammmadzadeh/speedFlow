"""Fetch processed_stream events for a scrape job (Postgres or Kafka fallback)."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SCRAPERS_ROOT = ROOT / "1-ingestion-edge" / "scrapers"
if str(SCRAPERS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPERS_ROOT))


def _preview(data: Any, max_len: int = 280) -> str:
    if data is None:
        return ""
    if isinstance(data, dict):
        for key in ("text", "title", "body", "html", "content", "raw"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                text_val = val.strip()
                return text_val[:max_len] + ("…" if len(text_val) > max_len else "")
        text_val = json.dumps(data, default=str)
    else:
        text_val = str(data)
    text_val = " ".join(text_val.split())
    return text_val[:max_len] + ("…" if len(text_val) > max_len else "")


def _parse_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
        except json.JSONDecodeError:
            return {"raw": payload}
    return {}


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    payload = _parse_payload(raw.get("payload"))
    original = payload.get("original") if isinstance(payload.get("original"), dict) else {}
    url = (
        original.get("_page_url")
        or original.get("url")
        or raw.get("url")
        or None
    )
    predictions = raw.get("predictions")
    if not predictions and isinstance(payload.get("predictions"), dict):
        predictions = payload.get("predictions")

    ts = raw.get("timestamp")
    processed_at = raw.get("processed_at")

    return {
        "event_id": raw.get("event_id"),
        "source_id": raw.get("source_id"),
        "vertical": raw.get("vertical"),
        "event_type": raw.get("event_type"),
        "timestamp": int(ts) if ts is not None else None,
        "processed_at": int(processed_at) if processed_at is not None else None,
        "url": url,
        "processing_strategy": raw.get("processing_strategy"),
        "confidence": raw.get("confidence"),
        "predictions": predictions or {},
        "content_preview": _preview(original or payload),
        "payload": payload,
    }


def _fetch_from_postgres(engine: Engine, source_id: str, limit: int) -> list[dict[str, Any]]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT event_id, source_id, vertical, event_type, timestamp, processed_at,
                           confidence, processing_strategy, payload
                    FROM processed_events
                    WHERE source_id = :sid
                    ORDER BY timestamp DESC
                    LIMIT :lim
                """),
                {"sid": source_id, "lim": limit},
            ).mappings().all()
        return [normalize_event(dict(r)) for r in rows]
    except Exception as exc:
        logger.warning("Postgres processed_events query failed: %s", exc)
        return []


def _fetch_from_kafka(source_id: str, limit: int) -> list[dict[str, Any]]:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
    topic = os.environ.get("KAFKA_PROCESSED_TOPIC", "processed_stream")
    schema_registry = os.environ.get("SCHEMA_REGISTRY_URL", "http://127.0.0.1:8081")
    os.environ.setdefault("SCHEMA_REGISTRY_URL", schema_registry)
    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", bootstrap)

    try:
        from confluent_kafka import Consumer, KafkaException, TopicPartition
        from confluent_kafka.schema_registry import SchemaRegistryClient
        from confluent_kafka.schema_registry.avro import AvroDeserializer
        from confluent_kafka.serialization import MessageField, SerializationContext
    except ImportError as exc:
        logger.warning("confluent_kafka not available for event lookup: %s", exc)
        return []

    schema_path = ROOT / "schemas" / "avro" / "processed_event.avsc"
    if not schema_path.exists():
        logger.warning("Avro schema missing: %s", schema_path)
        return []

    schema_str = schema_path.read_text()
    registry = SchemaRegistryClient({"url": schema_registry})
    deserializer = AvroDeserializer(registry, schema_str)

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"portal-events-{uuid.uuid4().hex[:12]}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })

    matches: list[dict[str, Any]] = []
    try:
        metadata = consumer.list_topics(topic, timeout=5)
        if topic not in metadata.topics:
            return []
        partitions = list(metadata.topics[topic].partitions.keys())
        tps = [TopicPartition(topic, p, 0) for p in partitions]
        consumer.assign(tps)

        deadline = time.time() + float(os.environ.get("KAFKA_EVENTS_SCAN_SEC", "10"))
        idle = 0
        max_idle = 8

        while time.time() < deadline and len(matches) < limit * 3:
            msg = consumer.poll(0.4)
            if msg is None:
                idle += 1
                if idle >= max_idle:
                    break
                continue
            idle = 0
            if msg.error():
                raise KafkaException(msg.error())
            ctx = SerializationContext(topic, MessageField.VALUE)
            value = deserializer(msg.value(), ctx)
            if not isinstance(value, dict):
                continue
            if value.get("source_id") != source_id:
                continue
            matches.append(normalize_event(value))
    except Exception as exc:
        logger.warning("Kafka processed_stream scan failed: %s", exc)
        return []
    finally:
        consumer.close()

    matches.sort(key=lambda e: e.get("timestamp") or 0, reverse=True)
    return matches[:limit]


def build_pipeline_steps(job: dict[str, Any], event_count: int) -> list[dict[str, Any]]:
    status = (job.get("status") or "unknown").lower()
    pages = int(job.get("pages_crawled") or 0)
    error_message = job.get("error_message")

    def step(name: str, via: str, st: str) -> dict[str, Any]:
        return {"name": name, "via": via, "status": st}

    no_data = status == "completed" and pages == 0
    if no_data:
        status = "failed"

    crawl_status = "done" if status == "completed" and pages > 0 else ("failed" if status == "failed" or no_data else "active")
    raw_status = "done" if pages > 0 or event_count > 0 else ("failed" if crawl_status == "failed" else ("active" if status == "running" else "pending"))
    processed_status = "done" if event_count > 0 else ("failed" if crawl_status == "failed" else ("active" if raw_status == "done" else "pending"))

    config = job.get("config") if isinstance(job.get("config"), dict) else {}
    if not config and job.get("config"):
        try:
            import json as _json
            parsed = _json.loads(job["config"]) if isinstance(job["config"], str) else job["config"]
            if isinstance(parsed, dict):
                config = parsed
        except Exception:
            config = {}
    engine = config.get("crawler_engine") or config.get("crawler_type") or "crawlee"
    engine_labels = {
        "fallback": "HTTP fallback crawl",
        "crawlee": "Crawlee + BeautifulSoup",
        "crawlee_playwright": "Crawlee + Playwright",
        "playwright": "Crawlee + Playwright",
        "beautifulsoup": "Crawlee + BeautifulSoup",
    }
    crawl_via = f"Redis queue → {engine_labels.get(str(engine), str(engine))}"
    steps = [
        step("Scrape submitted", "Platform API → orchestrator", "done"),
        step("Crawlee worker", crawl_via, crawl_status),
        step("raw_stream", "Kafka Avro publish", raw_status),
        step("Stream processor", "Flink-style aggregation", processed_status if raw_status == "done" else "pending"),
        step("processed_stream", "Results for this job", processed_status),
    ]
    if crawl_status == "failed" and error_message:
        steps[1]["error"] = str(error_message)
    elif no_data:
        steps[1]["error"] = "No pages were crawled"
    return steps


def fetch_job_events(
    engine: Engine,
    job_id: str,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))

    with engine.connect() as conn:
        job = conn.execute(
            text("""
                SELECT sj.*, t.name AS tenant_name
                FROM scrape_jobs sj
                LEFT JOIN tenants t ON t.tenant_id = sj.tenant_id
                WHERE sj.job_id = :jid
            """),
            {"jid": job_id},
        ).mappings().first()

    if not job:
        return {"found": False, "job_id": job_id, "events": [], "total": 0}

    job_dict = dict(job)
    tenant_id = job_dict["tenant_id"]
    source_id = f"{tenant_id}:{job_id}"

    events = _fetch_from_postgres(engine, source_id, limit)
    source = "postgres"
    if not events:
        events = _fetch_from_kafka(source_id, limit)
        source = "kafka" if events else "none"

    return {
        "found": True,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "tenant_name": job_dict.get("tenant_name"),
        "source_id": source_id,
        "job_status": job_dict.get("status"),
        "pages_crawled": job_dict.get("pages_crawled") or 0,
        "error_message": job_dict.get("error_message"),
        "requirement": job_dict.get("requirement"),
        "pipeline": build_pipeline_steps(job_dict, len(events)),
        "events": events,
        "total": len(events),
        "source": source,
    }
