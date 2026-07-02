"""Tenant quota and feature-flag middleware for Platform API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/features", "/metrics", "/docs", "/openapi.json", "/redoc"}
TENANT_CREATE_PATH = "/tenants"


class TenantQuotaMiddleware(BaseHTTPMiddleware):
    """Attach tenant context and enforce subscription feature flags on protected routes."""

    def __init__(self, app, get_plans, get_redis, resolve_tenant_fn, get_db_fn):
        super().__init__(app)
        self.get_plans = get_plans
        self.get_redis = get_redis
        self.resolve_tenant = resolve_tenant_fn
        self.get_db = get_db_fn

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        if path == TENANT_CREATE_PATH and request.method == "POST":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key and path.startswith("/scrape"):
            raise HTTPException(401, "Missing X-API-Key header")

        if api_key:
            db_gen = self.get_db()
            db = next(db_gen)
            try:
                tenant = self.resolve_tenant(db, api_key)
                plans = self.get_plans()
                plan = plans.get(tenant["plan"], plans.get("starter", {}))
                request.state.tenant = tenant
                request.state.plan = plan
                request.state.features = plan.get("features", {})
                request.state.limits = plan.get("limits", {})
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass

        if path.startswith("/scrape") and request.method == "POST":
            features = getattr(request.state, "features", {})
            if not features.get("ai_scrape_planner"):
                raise HTTPException(403, "Plan does not include AI scrape planning")

        response = await call_next(request)
        return response


async def get_daily_usage(redis, tenant_id: str) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"tenant:{tenant_id}:scrape_count:{today}"
    count = await redis.get(key)
    used = int(count) if count else 0
    return {"date": today, "scrape_requests_used": used}


async def enforce_daily_quota(redis, tenant_id: str, limit: int) -> int:
    key = f"tenant:{tenant_id}:scrape_count:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    if count > limit:
        await redis.decr(key)
        raise HTTPException(429, f"Daily scrape quota exceeded ({limit}/day)")
    return count
