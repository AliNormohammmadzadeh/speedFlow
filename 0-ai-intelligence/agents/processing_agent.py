"""Processing & ML Algorithm Selection Agent."""

import logging
from typing import Any

from shared.utils import AgentState, llm_complete

logger = logging.getLogger(__name__)


class ProcessingAgent:
    """Decides Flink vs ML vs aggregation and selects parameters."""

    name = "processing"

    STRATEGIES = {
        "flink_stateful": {"engine": "flink", "use_case": "rolling windows, joins, CEP"},
        "ml_cuda": {"engine": "ml_service", "use_case": "predictions, anomaly detection"},
        "simple_aggregation": {"engine": "stream_processor", "use_case": "basic transforms"},
    }

    async def run(self, state: AgentState, required_outcomes: list[str] | None = None) -> dict[str, Any]:
        outcomes = required_outcomes or ["market_signal", "momentum_prediction"]
        discovery = state.get("discovery_output", {})
        verticals = {s.get("vertical") for s in discovery.get("discovered_sources", [])}

        decisions = []
        for outcome in outcomes:
            strategy = self._select_strategy(outcome, verticals)
            params = self._generate_params(strategy, outcome)
            decisions.append({
                "outcome": outcome,
                "strategy": strategy,
                "parameters": params,
                "flink_config": params.get("flink", {}),
                "ml_config": params.get("ml", {}),
            })

        prompt = f"Select optimal processing for outcomes: {outcomes}"
        llm_choice = await llm_complete(prompt, system="You are a stream processing and ML architect.")

        result = {
            "processing_decisions": decisions,
            "primary_strategy": decisions[0]["strategy"] if decisions else "simple_aggregation",
            "llm_rationale": llm_choice,
        }
        state.set("processing_output", result)
        logger.info("Processing agent: %d decisions", len(decisions))
        return result

    def _select_strategy(self, outcome: str, verticals: set) -> str:
        if "signal" in outcome or "momentum" in outcome:
            return "flink_stateful"
        if "predict" in outcome or "forecast" in outcome:
            return "ml_cuda"
        if "financial_markets" in verticals:
            return "flink_stateful"
        return "simple_aggregation"

    def _generate_params(self, strategy: str, outcome: str) -> dict:
        if strategy == "flink_stateful":
            return {
                "flink": {"parallelism": 4, "window_size_seconds": 60, "job": "market_signal_processor"},
                "ml": {},
            }
        if strategy == "ml_cuda":
            return {
                "flink": {},
                "ml": {
                    "model_id": f"{outcome}_model",
                    "strategy": "ml_cuda",
                    "parameters": {"learning_rate": 0.01, "epochs": 10},
                    "feature_names": ["price", "momentum", "volume"],
                },
            }
        return {"flink": {}, "ml": {}}
