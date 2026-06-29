"""AI-Driven Data Monetization Marketplace API."""

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

logging.basicConfig(level=logging.INFO)

_products: list[dict] = []
_orders: list[dict] = []


def load_catalog() -> list[dict]:
    path = Path("/app/config/governance.yaml")
    if not path.exists():
        path = Path(__file__).parent.parent.parent / "config" / "business" / "governance.yaml"
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("data_products", {}).get("catalog", [])
    return []


class OrderRequest(BaseModel):
    product_id: str
    customer_id: str


class OrderResponse(BaseModel):
    order_id: str
    product_id: str
    price_usd: float
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _products
    _products = load_catalog()
    send_feedback(os.environ.get("APP_NAME", "data_marketplace"), {
        "api_calls": 1.0,
        "revenue_usd": 0.0,
    })
    yield


app = FastAPI(title="SpeedFlow Data Marketplace")


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
    product = next((p for p in _products if p["id"] == req.product_id), None)
    if not product:
        raise HTTPException(404, "Product not found")

    price = product.get("base_price_usd", 0.0)
    order = {
        "order_id": str(uuid.uuid4()),
        "product_id": req.product_id,
        "customer_id": req.customer_id,
        "price_usd": price,
        "status": "confirmed",
    }
    _orders.append(order)

    send_feedback(os.environ.get("APP_NAME", "data_marketplace"), {
        "api_calls": 1.0,
        "revenue_usd": price,
        "top_product_demand": 1.0,
    })
    return OrderResponse(**order)


@app.get("/demand/summary")
def demand_summary():
    """Market demand signal fed back to Strategy Agent."""
    by_product = {}
    for o in _orders:
        by_product[o["product_id"]] = by_product.get(o["product_id"], 0) + 1
    return {"orders_total": len(_orders), "demand_by_product": by_product}
