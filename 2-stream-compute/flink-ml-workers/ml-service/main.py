"""ML microservice - receives AI-selected model parameters and runs inference."""

import json
import logging
import os
from contextlib import asynccontextmanager

import numpy as np
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.linear_model import SGDRegressor

logger = logging.getLogger(__name__)

_models: dict[str, SGDRegressor] = {}
_redis: redis.Redis | None = None


class ModelConfig(BaseModel):
    model_id: str
    strategy: str = "ml_cuda"
    parameters: dict = {}
    feature_names: list[str] = ["price", "momentum"]


class InferenceRequest(BaseModel):
    model_id: str
    features: dict[str, float]


class InferenceResponse(BaseModel):
    model_id: str
    prediction: float
    confidence: float


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return _redis


def load_or_create_model(config: ModelConfig) -> SGDRegressor:
    if config.model_id not in _models:
        lr = config.parameters.get("learning_rate", 0.01)
        model = SGDRegressor(learning_rate="constant", eta0=lr, random_state=42)
        _models[config.model_id] = model
        # Warm-start with dummy data
        X = np.random.randn(10, len(config.feature_names))
        y = np.random.randn(10)
        model.partial_fit(X, y)
    return _models[config.model_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    # Listen for AI processing bridge updates
    client = get_redis()
    pubsub = client.pubsub()
    pubsub.subscribe("processing:config")
    logger.info("ML service started on :8090")
    yield
    pubsub.close()


app = FastAPI(title="SpeedFlow ML Service", lifespan=lifespan)


@app.post("/models/configure")
def configure_model(config: ModelConfig):
    """Processing Agent injects model parameters via this endpoint."""
    model = load_or_create_model(config)
    get_redis().set(f"ml:config:{config.model_id}", config.model_dump_json())
    logger.info("Configured model %s strategy=%s", config.model_id, config.strategy)
    return {"status": "configured", "model_id": config.model_id}


@app.post("/inference", response_model=InferenceResponse)
def run_inference(req: InferenceRequest):
    if req.model_id not in _models:
        raise HTTPException(404, f"Model {req.model_id} not configured")
    model = _models[req.model_id]
    config_raw = get_redis().get(f"ml:config:{req.model_id}")
    feature_names = json.loads(config_raw)["feature_names"] if config_raw else list(req.features.keys())
    X = np.array([[req.features.get(f, 0.0) for f in feature_names]])
    pred = float(model.predict(X)[0])
    return InferenceResponse(model_id=req.model_id, prediction=pred, confidence=0.75)


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": len(_models)}
