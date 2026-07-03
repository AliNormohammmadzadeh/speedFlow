"""Business Strategy & Goal Optimizer Agent."""

import logging
from typing import Any

from shared.utils import AgentState, load_yaml, llm_complete

logger = logging.getLogger(__name__)


class StrategyAgent:
    """Translates business goals into data gap requirements."""

    name = "strategy"

    async def run(
        self,
        state: AgentState,
        feedback: list[dict] | None = None,
        spend: dict | None = None,
    ) -> dict[str, Any]:
        metrics = load_yaml("business/metrics.yaml")
        verticals = load_yaml("business/verticals.yaml")
        kpis = metrics.get("primary_kpis", {})
        budget = metrics.get("budget_constraints", {})

        # FinOps loop (4.7): compare real spend to daily budgets and emit throttle
        # flags the orchestrator/bridges enforce.
        finops = self._finops_throttle(spend or {})

        feedback_summary = self._aggregate_feedback(feedback or [])
        composite_score = self._compute_composite_score(feedback_summary, kpis)

        gaps = []
        if composite_score < 0.5:
            gaps.append({"type": "data_volume", "priority": "high", "vertical": verticals.get("default_vertical")})
        if feedback_summary.get("trading_bot", {}).get("pnl_usd", 0) < 0:
            gaps.append({"type": "market_data_freshness", "priority": "critical", "vertical": "financial_markets"})
        if feedback_summary.get("data_marketplace", {}).get("api_calls", 0) > 1000:
            gaps.append({"type": "monetization_expansion", "priority": "medium"})

        prompt = f"""
        Given KPIs: {list(kpis.keys())}
        Composite score: {composite_score:.2f}
        Feedback: {feedback_summary}
        Budget: {budget}
        Identify top 3 data gaps to optimize revenue.
        """
        llm_analysis = await llm_complete(prompt, system="You are a business strategy AI for a data platform.")

        result = {
            "composite_score": composite_score,
            "data_gaps": gaps,
            "business_priorities": [
                {"goal": "maximize_revenue_per_kb", "weight": kpis.get("revenue_per_kilobyte", {}).get("weight", 0.25)},
                {"goal": "maximize_trading_profit", "weight": kpis.get("trading_profit_factor", {}).get("weight", 0.30)},
            ],
            "budget_remaining": finops["budget_remaining"],
            "budget_status": finops["budget_status"],
            "throttle": finops["throttle"],
            "llm_analysis": llm_analysis,
        }
        state.set("strategy_output", result)
        logger.info(
            "Strategy agent: composite_score=%.2f gaps=%d throttle=%s",
            composite_score, len(gaps), finops["throttle"],
        )
        return result

    def _finops_throttle(self, spend: dict) -> dict:
        """Load daily budgets and derive throttle flags from real spend."""
        cfg = load_yaml("finops/budgets.yaml")
        daily = (cfg.get("budgets", {}) or {}).get("daily", {})
        budgets = {
            "scrape": float(daily.get("scraping_usd", 500)),
            "compute": float(daily.get("compute_usd", 300)),
            "llm": float(daily.get("llm_usd", 100)),
        }

        def pct(cat: str) -> float:
            b = budgets.get(cat, 0)
            s = float(spend.get(cat, 0.0))
            return round(s / b, 3) if b else 0.0

        status = {cat: pct(cat) for cat in budgets}
        # Alert thresholds from budgets.yaml: 100% throttles that category, 110%
        # of scraping additionally pauses the Discovery Agent.
        throttle = {
            "scrapers": status["scrape"] >= 1.0,
            "compute": status["compute"] >= 1.0,
            "llm": status["llm"] >= 1.0,
            "pause_discovery": status["scrape"] >= 1.1,
        }
        remaining = {cat: round(budgets[cat] - float(spend.get(cat, 0.0)), 2) for cat in budgets}
        return {"budget_status": status, "throttle": throttle, "budget_remaining": remaining}

    def _aggregate_feedback(self, feedback: list[dict]) -> dict[str, dict]:
        agg: dict[str, dict] = {}
        for item in feedback:
            app = item.get("app_name", "unknown")
            if app not in agg:
                agg[app] = {}
            agg[app][item.get("metric_name", "value")] = item.get("metric_value", 0)
        return agg

    def _compute_composite_score(self, feedback: dict, kpis: dict) -> float:
        if not feedback:
            return 0.5
        scores = []
        trading = feedback.get("trading_bot", {})
        if "win_rate" in trading:
            scores.append(min(trading["win_rate"], 1.0))
        marketplace = feedback.get("data_marketplace", {})
        if "revenue_usd" in marketplace:
            scores.append(min(marketplace["revenue_usd"] / 1000, 1.0))
        return sum(scores) / len(scores) if scores else 0.5
