"""ML microservice - versioned model registry + hot reload via Processing Agent."""

import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import numpy as np
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.linear_model import SGDRegressor

logger = logging.getLogger(__name__)

# Active model instance per model_id (serves inference).
_models: dict[str, SGDRegressor] = {}
# In-memory registry mirror; also persisted to Redis for durability/restarts.
#   model_id -> {"active_version": int, "reload_count": int,
#                "last_reloaded_at": str, "versions": [ {version, strategy, ...} ]}
_registry: dict[str, dict] = {}
_redis: redis.Redis | None = None
_lock = threading.Lock()

REGISTRY_INDEX = "ml:registry:index"


class ModelConfig(BaseModel):
    model_id: str
    strategy: str = "ml_cuda"
    parameters: dict = {}
    feature_names: list[str] = ["price", "momentum"]
    version: int | None = None  # auto-assigned if omitted


class InferenceRequest(BaseModel):
    model_id: str
    features: dict[str, float]


class InferenceResponse(BaseModel):
    model_id: str
    prediction: float
    confidence: float
    version: int


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return _redis


def _build_model(config: dict) -> SGDRegressor:
    params = config.get("parameters", {})
    lr = params.get("learning_rate", 0.01)
    model = SGDRegressor(learning_rate="constant", eta0=lr, random_state=42)
    feature_names = config.get("feature_names", ["price", "momentum"])
    X = np.random.randn(10, len(feature_names))
    y = np.random.randn(10)
    model.partial_fit(X, y)
    return model


def _persist_registry(model_id: str) -> None:
    try:
        r = get_redis()
        r.set(f"ml:registry:{model_id}", json.dumps(_registry[model_id]))
        r.sadd(REGISTRY_INDEX, model_id)
    except Exception as exc:
        logger.warning("registry persist failed for %s: %s", model_id, exc)


def register_version(config: ModelConfig) -> dict:
    """Register a NEW model version and make it active (hot swap)."""
    with _lock:
        entry = _registry.setdefault(
            config.model_id, {"active_version": 0, "reload_count": 0, "last_reloaded_at": None, "versions": []}
        )
        version = config.version or (entry["active_version"] + 1)
        cfg_dict = config.model_dump()
        cfg_dict["version"] = version
        cfg_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        # Replace or append this version.
        entry["versions"] = [v for v in entry["versions"] if v["version"] != version]
        entry["versions"].append(cfg_dict)
        entry["active_version"] = version
        _models[config.model_id] = _build_model(cfg_dict)
        # Keep per-version config in Redis (used by /inference for feature order).
        get_redis().set(f"ml:config:{config.model_id}", json.dumps(cfg_dict))
        _persist_registry(config.model_id)
        logger.info("Registered model %s version=%s strategy=%s", config.model_id, version, config.strategy)
        return {"model_id": config.model_id, "version": version, "active_version": version}


def hot_reload(model_id: str) -> bool:
    """Rebuild the active model from its stored config without downtime.

    Triggered by the Processing Agent via the "processing:config" pub/sub channel.
    """
    with _lock:
        entry = _registry.get(model_id)
        if not entry or not entry["versions"]:
            # Try to recover config from Redis (e.g. after restart).
            raw = get_redis().get(f"ml:config:{model_id}")
            if not raw:
                logger.warning("hot_reload: no config for %s", model_id)
                return False
            cfg = json.loads(raw)
        else:
            active = entry["active_version"]
            cfg = next((v for v in entry["versions"] if v["version"] == active), entry["versions"][-1])
        _models[model_id] = _build_model(cfg)
        if entry:
            entry["reload_count"] += 1
            entry["last_reloaded_at"] = datetime.now(timezone.utc).isoformat()
            _persist_registry(model_id)
        logger.info("Hot-reloaded model %s (active v%s)", model_id, cfg.get("version"))
        return True


def _pubsub_listener():
    """Background thread: hot-reload models when the Processing Agent publishes."""
    while True:
        try:
            client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
            pubsub = client.pubsub()
            pubsub.subscribe("processing:config")
            logger.info("ML hot-reload listener subscribed to processing:config")
            for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    cfg = json.loads(message["data"])
                    model_id = cfg.get("model_id")
                    if model_id:
                        # Ensure the model exists (register if new) then hot reload.
                        if model_id not in _models:
                            register_version(ModelConfig(**cfg))
                        else:
                            hot_reload(model_id)
                except Exception as exc:
                    logger.warning("hot-reload message error: %s", exc)
        except Exception as exc:
            logger.warning("pubsub listener reconnecting after error: %s", exc)
            import time

            time.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    t = threading.Thread(target=_pubsub_listener, daemon=True)
    t.start()
    logger.info("ML service started on :8090")
    yield


app = FastAPI(title="SpeedFlow ML Service", lifespan=lifespan)


@app.post("/models/configure")
def configure_model(config: ModelConfig):
    """Processing Agent injects model parameters; registers a new active version."""
    result = register_version(config)
    return {"status": "configured", **result}


@app.post("/models/{model_id}/reload")
def reload_model(model_id: str):
    """Manually trigger a hot reload of the active model version."""
    if not hot_reload(model_id):
        raise HTTPException(404, f"Model {model_id} not found")
    return {"status": "reloaded", "model_id": model_id, **_registry.get(model_id, {})}


@app.get("/models")
def list_models():
    """List all registered models with their active version + reload count."""
    return {
        "count": len(_registry),
        "models": [
            {
                "model_id": mid,
                "active_version": e["active_version"],
                "versions": [v["version"] for v in e["versions"]],
                "reload_count": e["reload_count"],
                "last_reloaded_at": e["last_reloaded_at"],
            }
            for mid, e in _registry.items()
        ],
    }


@app.get("/models/{model_id}")
def get_model(model_id: str):
    entry = _registry.get(model_id)
    if not entry:
        raise HTTPException(404, f"Model {model_id} not found")
    return {"model_id": model_id, **entry}


@app.post("/inference", response_model=InferenceResponse)
def run_inference(req: InferenceRequest):
    if req.model_id not in _models:
        raise HTTPException(404, f"Model {req.model_id} not configured")
    model = _models[req.model_id]
    config_raw = get_redis().get(f"ml:config:{req.model_id}")
    cfg = json.loads(config_raw) if config_raw else {}
    feature_names = cfg.get("feature_names") or list(req.features.keys())
    version = cfg.get("version", _registry.get(req.model_id, {}).get("active_version", 1))
    X = np.array([[req.features.get(f, 0.0) for f in feature_names]])
    pred = float(model.predict(X)[0])
    return InferenceResponse(model_id=req.model_id, prediction=pred, confidence=0.75, version=version)


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": len(_models), "registered": len(_registry)}
