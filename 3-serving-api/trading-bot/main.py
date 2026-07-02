"""Real-time Trading Bot - consumes processed_stream signals."""

import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_AVRO = os.environ.get("USE_AVRO", "true").lower() in ("1", "true", "yes")

_signals: list[dict] = []
_pnl = 0.0
_wins = 0
_total = 0


class Signal(BaseModel):
    event_id: str
    symbol: str
    signal_type: str
    price: float | None
    confidence: float | None
    received_at: str


def _iter_events(topic: str, bootstrap: list[str]):
    """Yield processed-event dicts from Kafka, supporting both Avro and JSON wire formats."""
    if not USE_AVRO:
        from kafka import KafkaConsumer

        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap,
            auto_offset_reset="latest",
            group_id="trading-bot",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        logger.info("Trading bot consuming %s (json) from %s", topic, bootstrap)
        try:
            for msg in consumer:
                yield msg.value
        finally:
            consumer.close()
        return

    from confluent_kafka import Consumer
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroDeserializer
    from confluent_kafka.serialization import MessageField, SerializationContext

    sr_url = os.environ.get("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
    deserializer = AvroDeserializer(SchemaRegistryClient({"url": sr_url}))
    consumer = Consumer({
        "bootstrap.servers": ",".join(bootstrap),
        "group.id": "trading-bot",
        "auto.offset.reset": "latest",
    })
    consumer.subscribe([topic])
    logger.info("Trading bot consuming %s (avro) from %s", topic, bootstrap)
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                continue
            ctx = SerializationContext(msg.topic(), MessageField.VALUE)
            value = deserializer(msg.value(), ctx)
            if value is not None:
                yield value
    finally:
        consumer.close()


def consume_signals():
    global _pnl, _wins, _total
    topic = os.environ.get("KAFKA_PROCESSED_TOPIC", "processed_stream")
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
    while True:
        try:
            for event in _iter_events(topic, bootstrap):
                preds = event.get("predictions", {}) or {}
                signal_type = preds.get("signal", "hold")
                if signal_type == "hold":
                    continue
                _signals.append({
                    "event_id": event.get("event_id"),
                    "symbol": event.get("source_id", "UNKNOWN"),
                    "signal_type": signal_type,
                    "price": (event.get("features", {}) or {}).get("price"),
                    "confidence": event.get("confidence"),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                })
                if len(_signals) > 100:
                    _signals.pop(0)
                _total += 1
                pnl_delta = 10.0 if signal_type == "buy" else -5.0
                _pnl += pnl_delta
                if pnl_delta > 0:
                    _wins += 1
                if _total % 10 == 0:
                    send_feedback(os.environ.get("APP_NAME", "trading_bot"), {
                        "pnl_usd": _pnl,
                        "win_rate": _wins / _total if _total else 0,
                        "sharpe_ratio": 1.2,
                        "drawdown_pct": 5.0,
                    })
        except Exception as e:
            logger.error("Signal consumer error: %s — retrying in 5s", e)
            time.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=consume_signals, daemon=True)
    t.start()
    yield


app = FastAPI(title="SpeedFlow Trading Bot", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "signals_buffered": len(_signals), "pnl_usd": _pnl}


@app.get("/signals", response_model=list[Signal])
def get_signals():
    return _signals[-20:]


@app.get("/performance")
def performance():
    return {
        "pnl_usd": _pnl,
        "win_rate": _wins / _total if _total else 0,
        "total_trades": _total,
    }
