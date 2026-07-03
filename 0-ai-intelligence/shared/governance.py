"""Agent governance: drift detection + rollback per config/mlops/agent_governance.yaml.

Each agent has a registered version + drift_threshold. Evaluation scores are
tracked (Redis-backed); when an agent's score deviates from its baseline beyond
its threshold, governance flags drift and rolls the agent back to its last-good
version.
"""

import json
import logging
import os

import redis

from shared.utils import load_yaml

logger = logging.getLogger(__name__)


class AgentGovernance:
    def __init__(self):
        self.registry = load_yaml("mlops/agent_governance.yaml").get("agent_registry", {})
        self._redis = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

    def _key(self, agent: str) -> str:
        return f"governance:{agent}"

    def _state(self, agent: str) -> dict:
        raw = self._redis.get(self._key(agent))
        if raw:
            return json.loads(raw)
        spec = self.registry.get(agent, {})
        return {
            "agent": agent,
            "version": spec.get("version", "1.0.0"),
            "last_good_version": spec.get("version", "1.0.0"),
            "baseline": None,
            "current": None,
            "drift": 0.0,
            "status": "healthy",
            "rollbacks": 0,
        }

    def _save(self, state: dict) -> None:
        self._redis.set(self._key(state["agent"]), json.dumps(state))

    @staticmethod
    def _bump_patch(version: str) -> str:
        parts = version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
        except (ValueError, IndexError):
            return version
        return ".".join(parts)

    def evaluate(self, agent: str, score: float) -> dict:
        """Record an eval score, detect drift, and roll back if over threshold."""
        spec = self.registry.get(agent, {})
        threshold = float(spec.get("drift_threshold", 0.15))
        state = self._state(agent)

        if state["baseline"] is None:
            # First observation establishes the baseline for a healthy version.
            state["baseline"] = score
            state["current"] = score
            state["drift"] = 0.0
            state["status"] = "healthy"
            state["last_good_version"] = state["version"]
            self._save(state)
            return state

        baseline = state["baseline"]
        drift = abs(score - baseline) / (abs(baseline) if baseline else 1.0)
        state["current"] = score
        state["drift"] = round(drift, 4)

        if drift > threshold:
            # Drift detected → roll back to last-good version.
            state["status"] = "drift_detected"
            rolled_from = state["version"]
            state["version"] = state["last_good_version"]
            state["rollbacks"] += 1
            logger.warning(
                "Agent %s drift %.3f > %.3f — rolled back %s -> %s",
                agent, drift, threshold, rolled_from, state["version"],
            )
        else:
            state["status"] = "healthy"
            state["last_good_version"] = state["version"]
            # Slow baseline adaptation (EMA) while healthy.
            state["baseline"] = round(0.8 * baseline + 0.2 * score, 4)

        self._save(state)
        return state

    def promote(self, agent: str) -> dict:
        """Promote an agent to a new patch version after a validated change."""
        state = self._state(agent)
        state["version"] = self._bump_patch(state["version"])
        state["last_good_version"] = state["version"]
        state["status"] = "healthy"
        self._save(state)
        return state

    def status(self) -> dict:
        agents = {}
        for name, spec in self.registry.items():
            st = self._state(name)
            st["drift_threshold"] = spec.get("drift_threshold", 0.15)
            agents[name] = st
        return {"agents": agents}
