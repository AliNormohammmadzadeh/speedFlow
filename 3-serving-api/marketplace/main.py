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
        # Task 5.4: tenant-published datasets + revenue share.
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS marketplace_datasets ("
            "id SERIAL PRIMARY KEY, dataset_id VARCHAR(64) UNIQUE NOT NULL, "
            "publisher_tenant VARCHAR(64) NOT NULL, name VARCHAR(200) NOT NULL, "
            "description TEXT, vertical VARCHAR(100), price_usd DOUBLE PRECISION DEFAULT 0, "
            "revenue_share_pct DOUBLE PRECISION DEFAULT 70, sales_count INT DEFAULT 0, "
            "published BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS dataset_sales ("
            "id SERIAL PRIMARY KEY, sale_id VARCHAR(64) UNIQUE NOT NULL, dataset_id VARCHAR(64) NOT NULL, "
            "buyer_id VARCHAR(100) NOT NULL, price_usd DOUBLE PRECISION NOT NULL, "
            "publisher_earning_usd DOUBLE PRECISION NOT NULL, platform_fee_usd DOUBLE PRECISION NOT NULL, "
            "api_key VARCHAR(128), charge_id VARCHAR(128), created_at TIMESTAMPTZ DEFAULT NOW())"
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


DEFAULT_REVENUE_SHARE_PCT = float(os.environ.get("DATASET_REVENUE_SHARE_PCT", "70"))


class DatasetPublish(BaseModel):
    publisher_tenant: str
    name: str
    description: str = ""
    vertical: str | None = None
    price_usd: float = 0.0
    revenue_share_pct: float | None = None


class DatasetPurchase(BaseModel):
    buyer_id: str
    payment_token: str | None = None


@app.post("/datasets")
def publish_dataset(req: DatasetPublish):
    """Publish a tenant-owned dataset for sale with a revenue-share split."""
    from sqlalchemy import text

    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    share = req.revenue_share_pct if req.revenue_share_pct is not None else DEFAULT_REVENUE_SHARE_PCT
    share = max(0.0, min(100.0, share))
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO marketplace_datasets (dataset_id, publisher_tenant, name, description, "
                    "vertical, price_usd, revenue_share_pct) VALUES (:did, :pt, :name, :desc, :vert, :price, :share)"
                ),
                {"did": dataset_id, "pt": req.publisher_tenant, "name": req.name, "desc": req.description,
                 "vert": req.vertical, "price": req.price_usd, "share": share},
            )
    except Exception as exc:
        raise HTTPException(503, f"dataset publish failed: {exc}")
    return {
        "dataset_id": dataset_id, "publisher_tenant": req.publisher_tenant, "name": req.name,
        "price_usd": req.price_usd, "revenue_share_pct": share, "published": True,
    }


@app.get("/datasets")
def list_datasets(publisher_tenant: str | None = None):
    from sqlalchemy import text

    query = ("SELECT dataset_id, publisher_tenant, name, description, vertical, price_usd, "
             "revenue_share_pct, sales_count, published, created_at FROM marketplace_datasets "
             "WHERE published = TRUE")
    params: dict = {}
    if publisher_tenant:
        query += " AND publisher_tenant = :pt"
        params["pt"] = publisher_tenant
    query += " ORDER BY created_at DESC LIMIT 100"
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(query), params).mappings().all()
        return {"datasets": [dict(r) | {"created_at": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]}
    except Exception:
        return {"datasets": []}


@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    from sqlalchemy import text

    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT * FROM marketplace_datasets WHERE dataset_id = :did"), {"did": dataset_id}
        ).mappings().first()
    if not row:
        raise HTTPException(404, "Dataset not found")
    data = dict(row)
    if data.get("created_at"):
        data["created_at"] = data["created_at"].isoformat()
    return data


@app.post("/datasets/{dataset_id}/purchase")
def purchase_dataset(dataset_id: str, req: DatasetPurchase):
    """Buy a dataset; splits revenue between publisher and platform, delivers API key."""
    from sqlalchemy import text

    with get_engine().connect() as conn:
        ds = conn.execute(
            text("SELECT * FROM marketplace_datasets WHERE dataset_id = :did AND published = TRUE"),
            {"did": dataset_id},
        ).mappings().first()
    if not ds:
        raise HTTPException(404, "Dataset not found")

    price = float(ds["price_usd"])
    result = payments.charge(price, req.buyer_id, f"SpeedFlow dataset: {ds['name']}")
    if result["status"] not in ("succeeded", "no_charge"):
        raise HTTPException(402, f"Payment failed: {result['status']}")

    share_pct = float(ds["revenue_share_pct"])
    publisher_earning = round(price * share_pct / 100.0, 4)
    platform_fee = round(price - publisher_earning, 4)
    sale_id = f"sale_{uuid.uuid4().hex[:12]}"
    delivered_key = f"dp_{secrets.token_urlsafe(24)}"

    try:
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO dataset_sales (sale_id, dataset_id, buyer_id, price_usd, "
                    "publisher_earning_usd, platform_fee_usd, api_key, charge_id) "
                    "VALUES (:sid, :did, :bid, :price, :earn, :fee, :key, :charge)"
                ),
                {"sid": sale_id, "did": dataset_id, "bid": req.buyer_id, "price": price,
                 "earn": publisher_earning, "fee": platform_fee, "key": delivered_key, "charge": result["charge_id"]},
            )
            conn.execute(
                text("UPDATE marketplace_datasets SET sales_count = sales_count + 1 WHERE dataset_id = :did"),
                {"did": dataset_id},
            )
    except Exception as exc:
        raise HTTPException(503, f"sale persistence failed: {exc}")

    send_feedback(os.environ.get("APP_NAME", "data_marketplace"), {
        "api_calls": 1.0, "revenue_usd": platform_fee, "top_product_demand": 1.0,
    })
    return {
        "sale_id": sale_id, "dataset_id": dataset_id, "buyer_id": req.buyer_id,
        "price_usd": price, "publisher_earning_usd": publisher_earning,
        "platform_fee_usd": platform_fee, "revenue_share_pct": share_pct,
        "api_key": delivered_key, "charge_id": result["charge_id"], "provider": result["provider"],
    }


@app.get("/datasets/{dataset_id}/revenue")
def dataset_revenue(dataset_id: str):
    """Revenue-share report for a published dataset."""
    from sqlalchemy import text

    with get_engine().connect() as conn:
        ds = conn.execute(
            text("SELECT dataset_id, publisher_tenant, name, revenue_share_pct FROM marketplace_datasets WHERE dataset_id = :did"),
            {"did": dataset_id},
        ).mappings().first()
        if not ds:
            raise HTTPException(404, "Dataset not found")
        agg = conn.execute(
            text("SELECT COUNT(*) AS sales, COALESCE(SUM(price_usd),0) AS gross, "
                 "COALESCE(SUM(publisher_earning_usd),0) AS earnings, COALESCE(SUM(platform_fee_usd),0) AS fees "
                 "FROM dataset_sales WHERE dataset_id = :did"),
            {"did": dataset_id},
        ).mappings().first()
    return {
        "dataset_id": ds["dataset_id"],
        "publisher_tenant": ds["publisher_tenant"],
        "name": ds["name"],
        "revenue_share_pct": float(ds["revenue_share_pct"]),
        "total_sales": int(agg["sales"]),
        "gross_revenue_usd": round(float(agg["gross"]), 2),
        "publisher_earnings_usd": round(float(agg["earnings"]), 2),
        "platform_fees_usd": round(float(agg["fees"]), 2),
    }


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
