"""Accommodation Aggregator API - pilot end-use application."""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AccommodationResult(BaseModel):
    id: str
    name: str
    price_usd: float
    location: str
    rating: float | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    send_feedback(os.environ.get("APP_NAME", "accommodation_aggregator"), {
        "usage_sessions": 1.0,
        "conversion_rate": 0.03,
        "revenue_usd": 150.0,
    })
    yield


app = FastAPI(title="Accommodation Aggregator", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search", response_model=list[AccommodationResult])
def search(location: str = Query("Paris"), max_price: float = Query(500.0)):
    """Search accommodations (MVP with sample data)."""
    results = [
        AccommodationResult(id="acc-1", name=f"Hotel Central {location}", price_usd=120.0, location=location, rating=4.2),
        AccommodationResult(id="acc-2", name=f"Boutique Stay {location}", price_usd=89.0, location=location, rating=4.5),
        AccommodationResult(id="acc-3", name=f"Budget Inn {location}", price_usd=45.0, location=location, rating=3.8),
    ]
    filtered = [r for r in results if r.price_usd <= max_price]
    send_feedback(os.environ.get("APP_NAME", "accommodation_aggregator"), {
        "usage_sessions": 1.0,
        "revenue_usd": sum(r.price_usd * 0.05 for r in filtered),
    })
    return filtered
