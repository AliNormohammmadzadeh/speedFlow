"""Business Strategy & Goal Optimizer Agent."""

import logging
from typing import Any

from shared.utils import AgentState, load_yaml, llm_complete

logger = logging.getLogger(__name__)


class StrategyAgent:
    """Translates business goals into data gap requirements."""

    name = "strategy"

    async def run(self, state: AgentState, feedback: list[dict] | None = None) -> dict[str, Any]:
        metrics = load_yaml("business/metrics.yaml")
        verticals = load_yaml("business/verticals.yaml")
        kpis = metrics.get("primary_kpis", {})
        budget = metrics.get("budget_constraints", {})

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
            "budget_remaining": {
                "scraping": budget.get("daily_scraping_budget_usd", 500),
                "compute": budget.get("daily_compute_budget_usd", 300),
            },
            "llm_analysis": llm_analysis,
        }
        state.set("strategy_output", result)
        logger.info("Strategy agent: composite_score=%.2f gaps=%d", composite_score, len(gaps))
        return result

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
