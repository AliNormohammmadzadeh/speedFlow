"""AI-to-Processing Bridge: Processing Agent -> Flink/ML service."""

import json
import logging
import os

import httpx
import redis

logger = logging.getLogger(__name__)

QUEUE_KEY = os.environ.get("PROCESSING_BRIDGE_QUEUE", "processing:jobs")
ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8090")


class ProcessingBridge:
    def __init__(self):
        self.redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

    def inject_decisions(self, decisions: list[dict]) -> dict:
        results = {"ml_configured": 0, "flink_queued": 0, "errors": []}
        for decision in decisions:
            ml_config = decision.get("ml_config") or decision.get("parameters", {}).get("ml", {})
            if ml_config and ml_config.get("model_id"):
                try:
                    with httpx.Client(timeout=10) as client:
                        resp = client.post(f"{ML_SERVICE_URL}/models/configure", json=ml_config)
                        resp.raise_for_status()
                    self.redis.publish("processing:config", json.dumps(ml_config))
                    results["ml_configured"] += 1
                except Exception as e:
                    results["errors"].append(str(e))

            flink_config = decision.get("flink_config") or decision.get("parameters", {}).get("flink", {})
            if flink_config:
                self.redis.rpush(QUEUE_KEY, json.dumps({"type": "flink", "config": flink_config}))
                results["flink_queued"] += 1

        logger.info("Processing bridge: ml=%d flink=%d", results["ml_configured"], results["flink_queued"])
        return results

    def inject_flink_code(self, job_name: str, code: str) -> None:
        """Phase 4: inject dynamic Flink function code."""
        payload = {"type": "flink_code", "job_name": job_name, "code": code}
        self.redis.rpush(QUEUE_KEY, json.dumps(payload))
        logger.info("Queued Flink code injection for job: %s", job_name)
