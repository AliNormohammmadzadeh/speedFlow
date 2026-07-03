"""AI-Driven Data Monetization Marketplace API — v2 (Stripe, usage pricing, API keys)."""

import logging
import os
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

import payments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = (
    f"postgresql://{os.environ.get('POSTGRES_USER', 'admin')}:"
    f"{os.environ.get('POSTGRES_PASSWORD', 'adminpassword')}@"
    f"{os.environ.get('POSTGRES_HOST', 'postgres')}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ.get('POSTGRES_DB', 'platform_db')}"
)

_products: list[dict] = []
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def _ensure_tables() -> None:
    from sqlalchemy import text

    with get_engine().begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS marketplace_api_keys ("
            "id SERIAL PRIMARY KEY, order_id VARCHAR(64) NOT NULL, product_id VARCHAR(100) NOT NULL, "
            "customer_id VARCHAR(100) NOT NULL, api_key VARCHAR(128) UNIQUE NOT NULL, "
            "created_at TIMESTAMPTZ DEFAULT NOW())"
        ))
        conn.execute(text(
            "ALTER TABLE marketplace_orders ADD COLUMN IF NOT EXISTS order_id VARCHAR(64)"
        ))
        conn.execute(text(
            "ALTER TABLE marketplace_orders ADD COLUMN IF NOT EXISTS charge_id VARCHAR(128)"
        ))
        conn.execute(text(
            "ALTER TABLE marketplace_orders ADD COLUMN IF NOT EXISTS quantity INT DEFAULT 1"
        ))


def load_catalog() -> list[dict]:
    path = Path("/app/config/governance.yaml")
    if not path.exists():
        path = Path(__file__).parent.parent.parent / "config" / "business" / "governance.yaml"
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("data_products", {}).get("catalog", [])
    return []


def compute_charge(product: dict, quantity: int) -> float:
    """Usage-based pricing by product pricing_model."""
    model = product.get("pricing_model", "subscription_monthly")
    base = float(product.get("base_price_usd", 0.0))
    if model == "per_api_call":
        return round(base * max(1, quantity), 4)
    if model == "subscription_monthly":
        return base
    if model == "revenue_share":
        return 0.0  # billed later from realized revenue
    return base


class OrderRequest(BaseModel):
    product_id: str
    customer_id: str
    quantity: int = 1
    payment_token: str | None = None


class OrderResponse(BaseModel):
    order_id: str
    product_id: str
    price_usd: float
    status: str
    charge_id: str | None = None
    provider: str
    api_key: str
    pricing_model: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _products
    _products = load_catalog()
    try:
        _ensure_tables()
    except Exception as exc:
        logger.warning("table init failed: %s", exc)
    send_feedback(os.environ.get("APP_NAME", "data_marketplace"), {"api_calls": 1.0, "revenue_usd": 0.0})
    yield


app = FastAPI(title="SpeedFlow Data Marketplace", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "products": len(_products)}


@app.get("/products")
def list_products():
    send_feedback(os.environ.get("APP_NAME", "data_marketplace"), {"api_calls": 1.0})
    return {"products": _products}


@app.get("/products/{product_id}")
def get_product(product_id: str):
    product = next((p for p in _products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@app.post("/orders", response_model=OrderResponse)
def create_order(req: OrderRequest, x_api_key: str = Header(default="demo")):
    from sqlalchemy import text

    product = next((p for p in _products if p["id"] == req.product_id), None)
    if not product:
        raise HTTPException(404, "Product not found")

    price = compute_charge(product, req.quantity)
    # 1) Process payment through the gateway (Stripe or mock).
    result = payments.charge(price, req.customer_id, f"SpeedFlow: {product['name']}")
    if result["status"] not in ("succeeded", "no_charge"):
        raise HTTPException(402, f"Payment failed: {result['status']}")

    order_id = str(uuid.uuid4())
    # 2) Automated API key delivery for the purchased data product.
    delivered_key = f"dp_{secrets.token_urlsafe(24)}"

    # 3) Persist order + delivered key to Postgres.
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO marketplace_orders (order_id, product_id, customer_id, price_usd, status, charge_id, quantity) "
                    "VALUES (:oid, :pid, :cid, :price, :status, :charge, :qty)"
                ),
                {"oid": order_id, "pid": req.product_id, "cid": req.customer_id, "price": price,
                 "status": "confirmed", "charge": result["charge_id"], "qty": req.quantity},
            )
            conn.execute(
                text(
                    "INSERT INTO marketplace_api_keys (order_id, product_id, customer_id, api_key) "
                    "VALUES (:oid, :pid, :cid, :key)"
                ),
                {"oid": order_id, "pid": req.product_id, "cid": req.customer_id, "key": delivered_key},
            )
    except Exception as exc:
        logger.warning("order persistence failed: %s", exc)

    send_feedback(os.environ.get("APP_NAME", "data_marketplace"), {
        "api_calls": 1.0, "revenue_usd": price, "top_product_demand": 1.0,
    })
    return OrderResponse(
        order_id=order_id,
        product_id=req.product_id,
        price_usd=price,
        status="confirmed",
        charge_id=result["charge_id"],
        provider=result["provider"],
        api_key=delivered_key,
        pricing_model=product.get("pricing_model", "subscription_monthly"),
    )


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    from sqlalchemy import text

    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT order_id, product_id, customer_id, price_usd, status, charge_id, quantity, created_at "
                 "FROM marketplace_orders WHERE order_id = :oid"),
            {"oid": order_id},
        ).mappings().first()
    if not row:
        raise HTTPException(404, "Order not found")
    return dict(row)


@app.get("/demand/summary")
def demand_summary():
    """Market demand signal fed back to Strategy Agent (from Postgres)."""
    from sqlalchemy import text

    try:
        with get_engine().connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM marketplace_orders")).scalar() or 0
            rows = conn.execute(
                text("SELECT product_id, COUNT(*) AS c FROM marketplace_orders GROUP BY product_id")
            ).mappings().all()
        return {"orders_total": int(total), "demand_by_product": {r["product_id"]: r["c"] for r in rows}}
    except Exception:
        return {"orders_total": 0, "demand_by_product": {}}
