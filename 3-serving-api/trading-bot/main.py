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
from kafka import KafkaConsumer
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def consume_signals():
    global _pnl, _wins, _total
    topic = os.environ.get("KAFKA_PROCESSED_TOPIC", "processed_stream")
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
    while True:
        consumer = None
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap,
                auto_offset_reset="latest",
                group_id="trading-bot",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            logger.info("Trading bot consuming %s from %s", topic, bootstrap)
            for msg in consumer:
                event = msg.value
                preds = event.get("predictions", {})
                signal_type = preds.get("signal", "hold")
                if signal_type == "hold":
                    continue
                _signals.append({
                    "event_id": event.get("event_id"),
                    "symbol": event.get("source_id", "UNKNOWN"),
                    "signal_type": signal_type,
                    "price": event.get("features", {}).get("price"),
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
        finally:
            if consumer is not None:
                try:
                    consumer.close()
                except Exception:
                    pass


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
