"""Shared feedback client for end-use apps."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def send_feedback(app_name: str, metrics: dict[str, float]) -> bool:
    url = os.environ.get("AI_ORCHESTRATOR_URL", "http://ai-orchestrator:8000")
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.post(f"{url}/feedback", json={"app_name": app_name, "metrics": metrics})
            resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Feedback send failed: %s", e)
        return False
