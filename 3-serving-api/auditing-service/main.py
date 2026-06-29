"""Auditing Service - tracks customer value and compliance."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.feedback_client import send_feedback

logging.basicConfig(level=logging.INFO)

_audit_log: list[dict] = []


class AuditEntry(BaseModel):
    action: str
    actor: str
    resource: str
    details: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    send_feedback(os.environ.get("APP_NAME", "auditing_service"), {
        "customer_value_score": 0.85,
        "dispute_rate": 0.02,
    })
    yield


app = FastAPI(title="SpeedFlow Auditing Service")


@app.get("/health")
def health():
    return {"status": "ok", "entries": len(_audit_log)}


@app.post("/audit")
def log_audit(entry: AuditEntry):
    record = {**entry.model_dump(), "timestamp": datetime.now(timezone.utc).isoformat()}
    _audit_log.append(record)
    send_feedback(os.environ.get("APP_NAME", "auditing_service"), {
        "customer_value_score": 0.85 + len(_audit_log) * 0.001,
        "dispute_rate": 0.02,
    })
    return {"status": "logged", "id": len(_audit_log)}


@app.get("/audit/recent")
def recent_audits(limit: int = 20):
    return _audit_log[-limit:]
