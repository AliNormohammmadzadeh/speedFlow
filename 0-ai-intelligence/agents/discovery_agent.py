"""Data Source Discovery & Valuation Agent."""

import logging
from typing import Any

from shared.utils import AgentState, load_yaml, llm_complete

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    """Identifies high-value data sources and assigns value scores."""

    name = "discovery"

    async def run(self, state: AgentState, data_gaps: list[dict] | None = None) -> dict[str, Any]:
        verticals = load_yaml("business/verticals.yaml")
        gaps = data_gaps or state.get("strategy_output", {}).get("data_gaps", [])

        discovered = []
        for vid, vertical in verticals.get("verticals", {}).items():
            for source in vertical.get("seed_sources", []):
                score = self._score_source(source, gaps)
                discovered.append({
                    "source_id": source["name"],
                    "type": source["type"],
                    "url": source["url"],
                    "vertical": vid,
                    "value_score": score,
                    "action": "enable" if score > 0.6 else "monitor",
                })

        # Simulate discovery from metadata (extend with GitHub/search API)
        for gap in gaps:
            if gap.get("type") == "market_data_freshness":
                discovered.append({
                    "source_id": "discovered_binance_futures",
                    "type": "websocket",
                    "url": "wss://fstream.binance.com/ws/btcusdt@aggTrade",
                    "vertical": "financial_markets",
                    "value_score": 0.92,
                    "action": "enable",
                    "ai_discovered": True,
                })

        prompt = f"Evaluate these sources for a data platform: {discovered[:5]}"
        llm_eval = await llm_complete(prompt, system="You score data sources by revenue potential.")

        result = {
            "discovered_sources": sorted(discovered, key=lambda x: x["value_score"], reverse=True),
            "scraping_targets": [s for s in discovered if s["action"] == "enable"],
            "llm_evaluation": llm_eval,
        }
        state.set("discovery_output", result)
        logger.info("Discovery agent: found %d sources, %d targets", len(discovered), len(result["scraping_targets"]))
        return result

    def _score_source(self, source: dict, gaps: list[dict]) -> float:
        base = source.get("value_score", 0.5)
        for gap in gaps:
            if gap.get("vertical") and gap["vertical"] in source.get("name", ""):
                base += 0.1
        return min(base, 1.0)
