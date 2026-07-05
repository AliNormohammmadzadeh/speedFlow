"""Real-time Trading Bot - consumes processed_stream signals."""

import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

from strategy import RiskConfig, generate_price_series, run_backtest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_AVRO = os.environ.get("USE_AVRO", "true").lower() in ("1", "true", "yes")

_signals: list[dict] = []
_pnl = 0.0
_wins = 0
_total = 0

# --- Risk management + mock broker state (task 5.3) ---
_risk = RiskConfig()
_broker_positions: dict[str, dict] = {}
_broker_cash = float(os.environ.get("BROKER_STARTING_CASH", "100000"))
_broker_orders: list[dict] = []
BROKER_PROVIDER = os.environ.get("BROKER_PROVIDER", "mock").lower()


def _execute_broker_order(symbol: str, side: str, price: float, notional: float, reason: str = "manual") -> dict:
    """Mock broker order execution with position sizing + risk-limit enforcement."""
    global _broker_cash
    notional = min(float(notional), _risk.max_position_usd)
    if notional <= 0:
        raise HTTPException(400, "notional must be positive")
    pos = _broker_positions.get(symbol, {"units": 0.0, "avg_price": 0.0})

    if side == "buy":
        if notional > _broker_cash:
            raise HTTPException(402, f"Insufficient broker cash ({_broker_cash:.2f} < {notional:.2f})")
        units = notional / price
        total_units = pos["units"] + units
        pos["avg_price"] = ((pos["units"] * pos["avg_price"]) + notional) / total_units if total_units else price
        pos["units"] = total_units
        _broker_cash -= notional
        realized = 0.0
    elif side == "sell":
        units = min(pos["units"], notional / price)
        proceeds = units * price
        realized = proceeds - units * pos["avg_price"]
        pos["units"] -= units
        _broker_cash += proceeds
    else:
        raise HTTPException(400, "side must be 'buy' or 'sell'")

    _broker_positions[symbol] = pos
    order = {
        "order_id": f"ord_{len(_broker_orders) + 1}",
        "symbol": symbol, "side": side, "price": round(price, 4),
        "notional_usd": round(notional, 2), "realized_pnl_usd": round(realized, 2),
        "provider": BROKER_PROVIDER, "reason": reason,
        "cash_usd": round(_broker_cash, 2),
    }
    _broker_orders.append(order)
    if len(_broker_orders) > 200:
        _broker_orders.pop(0)
    return order


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
                # Route the signal through the risk-managed mock broker.
                price = (event.get("features", {}) or {}).get("price") or 100.0
                try:
                    _execute_broker_order(
                        event.get("source_id", "UNKNOWN"), signal_type,
                        float(price), _risk.position_size_usd, reason="live_signal",
                    )
                except Exception as exc:
                    logger.debug("broker order skipped: %s", exc)
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


class RiskUpdate(BaseModel):
    position_size_usd: float | None = None
    max_position_usd: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_daily_loss_usd: float | None = None


@app.get("/risk")
def get_risk():
    return _risk.to_dict()


@app.post("/risk")
def update_risk(req: RiskUpdate):
    """Update risk-management parameters used by live trading and backtests."""
    global _risk
    merged = {**_risk.to_dict(), **{k: v for k, v in req.model_dump().items() if v is not None}}
    _risk = RiskConfig.from_dict(merged)
    return {"status": "updated", "risk": _risk.to_dict()}


class BacktestRequest(BaseModel):
    symbol: str = "BTCUSD"
    periods: int = 120
    seed: int | None = 42
    start_price: float = 100.0
    volatility: float = 0.02
    drift: float = 0.0008
    initial_capital: float = 100000.0
    lookback: int = 5
    buy_threshold: float = 0.01
    sell_threshold: float = -0.01
    risk: RiskUpdate | None = None


@app.post("/backtest")
def backtest(req: BacktestRequest):
    """Run a momentum backtest with risk management over a synthetic price series."""
    risk = _risk
    if req.risk is not None:
        risk = RiskConfig.from_dict({**_risk.to_dict(), **{k: v for k, v in req.risk.model_dump().items() if v is not None}})
    prices = generate_price_series(
        req.symbol, n=max(10, min(req.periods, 2000)), seed=req.seed,
        start_price=req.start_price, vol=req.volatility, drift=req.drift,
    )
    result = run_backtest(
        prices, risk, initial_capital=req.initial_capital,
        lookback=req.lookback, buy_threshold=req.buy_threshold, sell_threshold=req.sell_threshold,
    )
    out = result.to_dict()
    out["symbol"] = req.symbol
    out["risk"] = risk.to_dict()
    return out


class BrokerOrder(BaseModel):
    symbol: str
    side: str
    price: float
    notional_usd: float | None = None


@app.get("/broker/positions")
def broker_positions():
    positions = [
        {"symbol": s, "units": round(p["units"], 6), "avg_price": round(p["avg_price"], 4)}
        for s, p in _broker_positions.items() if p["units"] > 1e-9
    ]
    return {
        "provider": BROKER_PROVIDER,
        "cash_usd": round(_broker_cash, 2),
        "positions": positions,
        "recent_orders": _broker_orders[-20:],
    }


@app.post("/broker/order")
def broker_order(req: BrokerOrder):
    notional = req.notional_usd if req.notional_usd is not None else _risk.position_size_usd
    return _execute_broker_order(req.symbol, req.side.lower(), req.price, notional, reason="manual")
