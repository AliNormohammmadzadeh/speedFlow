"""Kafka stream processor: raw_stream -> stateful processing -> processed_stream."""

import json
import logging
import os
import signal
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from shared.kafka_avro import create_consumer, create_processed_producer, register_schemas
from pii import BLOCK_ON_PII, PII_ENABLED, redact

logging.basicConfig(level=logging.INFO, format="%(asctime)s [processor] %(message)s")
logger = logging.getLogger(__name__)

# --- Prometheus metrics ---
try:
    from prometheus_client import Counter, Gauge, start_http_server

    EVENTS_PROCESSED = Counter("speedflow_events_processed_total", "Events processed", ["strategy"])
    PROCESS_ERRORS = Counter("speedflow_processing_errors_total", "Processing errors")
    INDEX_ERRORS = Counter("speedflow_search_index_errors_total", "Search index errors")
    WINDOW_STATE = Gauge("speedflow_rolling_window_keys", "Active rolling-window source keys")
    _METRICS = True
except Exception:  # prometheus-client optional
    _METRICS = False

METRICS_PORT = int(os.environ.get("METRICS_PORT", "9308"))

SEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "").rstrip("/")
SEARCH_INDEX = os.environ.get("SEARCH_INDEX", "processed-events")


def index_to_search(event: dict) -> None:
    """App-level OpenSearch/Elasticsearch indexer (Connect ES sink rejects OpenSearch)."""
    if not SEARCH_URL:
        return
    try:
        body = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            f"{SEARCH_URL}/{SEARCH_INDEX}/_doc/{event['event_id']}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as exc:  # indexing is best-effort, never block the pipeline
        if _METRICS:
            INDEX_ERRORS.inc()
        logger.warning("Search indexing failed for %s: %s", event.get("event_id"), exc)

_state: dict[str, list[float]] = defaultdict(list)
_running = True


def handle_signal(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def extract_numeric_features(payload: dict) -> dict[str, float]:
    features = {}
    if isinstance(payload, dict):
        for key, val in payload.items():
            if isinstance(val, (int, float)):
                features[key] = float(val)
            elif isinstance(val, str):
                try:
                    features[key] = float(val)
                except ValueError:
                    pass
        if "price" in payload:
            features["price"] = float(payload["price"])
        if "p" in payload:
            features["price"] = float(payload["p"])
        if "q" in payload:
            features["quantity"] = float(payload["q"])
    return features


def compute_rolling_stats(source_id: str, price: float) -> dict[str, float]:
    window = _state[source_id]
    window.append(price)
    if len(window) > 100:
        window.pop(0)
    avg = sum(window) / len(window)
    momentum = (price - window[0]) / window[0] if window[0] else 0.0
    return {"rolling_avg": avg, "momentum": momentum, "window_size": len(window)}


def process_event(raw: dict) -> dict:
    payload_str = raw.get("payload", "{}")
    try:
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    except json.JSONDecodeError:
        payload = {"raw": payload_str}

    # PII redaction (compliance 4.3): scrub sensitive fields/values before the
    # payload is persisted to Postgres/OpenSearch. Numeric features are computed
    # from the redacted payload (PII fields are non-numeric, so no signal loss).
    pii_redacted = 0
    if PII_ENABLED:
        payload, pii_redacted = redact(payload)

    features = extract_numeric_features(payload)
    strategy = "simple_aggregation"

    if features.get("price"):
        stats = compute_rolling_stats(raw["source_id"], features["price"])
        features.update(stats)
        strategy = "flink_stateful"

    predictions = {}
    if "momentum" in features:
        signal_val = "buy" if features["momentum"] > 0.01 else "sell" if features["momentum"] < -0.01 else "hold"
        predictions["signal"] = signal_val
        predictions["momentum"] = str(features["momentum"])

    return {
        "event_id": raw.get("event_id", str(uuid.uuid4())),
        "source_id": raw["source_id"],
        "vertical": raw.get("vertical", "unknown"),
        "event_type": f"processed_{raw.get('event_type', 'event')}",
        "timestamp": raw.get("timestamp", int(time.time() * 1000)),
        "processed_at": int(datetime.now(timezone.utc).timestamp() * 1000),
        "features": features,
        "predictions": predictions,
        "confidence": min(abs(features.get("momentum", 0)) * 10, 1.0) if features else None,
        "processing_strategy": strategy,
        "payload": json.dumps({
            "original": payload,
            "features": features,
            "predictions": predictions,
            "pii_redacted": pii_redacted,
        }),
    }


def main():
    raw_topic = os.environ.get("KAFKA_RAW_TOPIC", "raw_stream")
    # Subscribe by regex so per-tenant dedicated topics (raw_stream_<tenant_id>)
    # are consumed automatically as they are created, alongside the shared topic.
    raw_pattern = os.environ.get("KAFKA_RAW_TOPIC_PATTERN", "^raw_stream.*")
    processed_topic = os.environ.get("KAFKA_PROCESSED_TOPIC", "processed_stream")

    try:
        register_schemas()
    except Exception as exc:
        logger.warning("Schema registration skipped: %s", exc)

    topics = [raw_pattern] if raw_pattern else [raw_topic]
    consumer = create_consumer(topics, "speedflow-stream-processor", "raw_event.avsc")
    producer = create_processed_producer()

    if _METRICS:
        try:
            start_http_server(METRICS_PORT)
            logger.info("Prometheus metrics on :%d/metrics", METRICS_PORT)
        except Exception as exc:
            logger.warning("metrics server failed: %s", exc)

    logger.info("Stream processor started: %s -> %s", topics, processed_topic)

    while _running:
        records = consumer.poll(timeout_ms=1000)
        for tp, messages in records.items():
            for msg in messages:
                try:
                    raw = msg.value if hasattr(msg, "value") and not isinstance(msg, dict) else msg.get("value", msg)
                    processed = process_event(raw)
                    producer.send(processed_topic, key=processed["source_id"], value=processed)
                    producer.flush()
                    index_to_search(processed)
                    if _METRICS:
                        EVENTS_PROCESSED.labels(strategy=processed["processing_strategy"]).inc()
                        WINDOW_STATE.set(len(_state))
                    logger.info("Processed event %s strategy=%s", processed["event_id"], processed["processing_strategy"])
                except Exception as e:
                    if _METRICS:
                        PROCESS_ERRORS.inc()
                    logger.error("Processing error: %s", e)

    consumer.close()


if __name__ == "__main__":
    main()
