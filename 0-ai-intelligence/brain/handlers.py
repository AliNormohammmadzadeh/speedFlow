"""Step-action handlers that drive the live SpeedFlow agent swarm + services.

These bind the Brain's declarative ``action`` names to real work: running an
agent, planning a scrape, or health-checking a downstream service. Handlers are
deliberately defensive — a downstream being unavailable returns a structured
status the verifier can examine, rather than throwing, so the Brain can report
exactly which parts are (and aren't) running.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_orchestrator_handlers(
    *,
    scrape_planner,
    strategy_agent,
    discovery_agent,
    processing_agent,
    config_agent,
    services: dict[str, str] | None = None,
    vertical_registry=None,
) -> dict[str, Any]:
    services = services or {}

    def _state(ctx):
        st = ctx.deps.get("_agent_state")
        if st is None:
            from shared.utils import AgentState

            st = AgentState()
            ctx.deps["_agent_state"] = st
        return st

    def resolve(ctx, step):
        """Materialize the resolved config for a planning/resolution step."""
        return {"status": "ok", "resolved": dict(step.config)}

    async def plan_scrape(ctx, step):
        cfg = step.config
        plan = await scrape_planner.plan_from_requirement(
            cfg.get("requirement", ""),
            tenant_id=cfg.get("tenant_id"),
            hints=cfg.get("hints", {}),
        )
        return plan

    async def run_strategy(ctx, step):
        out = await strategy_agent.run(
            _state(ctx),
            feedback=step.config.get("feedback", []),
            spend=step.config.get("spend", {}),
        )
        return out

    async def run_discovery(ctx, step):
        state = _state(ctx)
        data_gaps = (state.get("strategy_output") or {}).get("data_gaps")
        return await discovery_agent.run(state, data_gaps=data_gaps)

    async def run_processing(ctx, step):
        return await processing_agent.run(
            _state(ctx), required_outcomes=step.config.get("required_outcomes") or None
        )

    async def run_config(ctx, step):
        return await config_agent.run(_state(ctx), desired_state=step.config.get("desired_state") or None)

    async def check_service(ctx, step):
        import httpx

        name = step.config.get("service", "")
        path = step.config.get("path", "/health")
        url = services.get(name)
        if not url:
            return {"service": name, "status": "unknown", "error": "no service url configured"}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{url}{path}")
                return {
                    "service": name,
                    "status": "up" if r.status_code < 400 else "degraded",
                    "code": r.status_code,
                }
        except Exception as exc:
            return {"service": name, "status": "down", "error": str(exc)}

    async def register_vertical(ctx, step):
        if vertical_registry is None:
            return {"status": "skipped", "reason": "no vertical registry"}
        try:
            spec = vertical_registry.register(step.config.get("vertical", {}))
            return {"status": "registered", "vertical": spec}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    return {
        "noop": resolve,
        "resolve": resolve,
        "plan_scrape": plan_scrape,
        "run_strategy": run_strategy,
        "run_discovery": run_discovery,
        "run_processing": run_processing,
        "run_config": run_config,
        "check_service": check_service,
        "register_vertical": register_vertical,
    }
