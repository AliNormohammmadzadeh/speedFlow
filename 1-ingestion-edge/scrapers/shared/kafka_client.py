"""Shared utilities for all scraper types."""

import json
import os
import time
import uuid
from datetime import datetime, timezone

from shared.kafka_avro import USE_AVRO, create_producer as _create_producer, register_schemas


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def create_producer():
    try:
        register_schemas()
    except Exception:
        pass
    return _create_producer()


def build_raw_event(
    source_id: str,
    source_type: str,
    vertical: str,
    event_type: str,
    payload: dict,
    url: str | None = None,
    value_score: float | None = None,
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "source_id": str(source_id),
        "source_type": source_type,
        "vertical": str(vertical or "unknown"),
        "event_type": str(event_type or "event"),
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        "url": url,
        "payload": json.dumps(payload) if isinstance(payload, dict) else str(payload),
        "metadata": {},
        "value_score": value_score,
    }


def publish_event(producer, event: dict, topic: str | None = None) -> None:
    dest = topic or get_env("KAFKA_RAW_TOPIC", "raw_stream")
    producer.send(dest, key=event["source_id"], value=event)
    producer.flush()


def now_ms() -> int:
    return int(time.time() * 1000)
