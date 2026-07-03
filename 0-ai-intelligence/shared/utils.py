"""Shared utilities for AI agents."""

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def load_yaml(relative_path: str) -> dict:
    base = Path(os.environ.get("CONFIG_PATH", "/app/config"))
    path = base / relative_path
    if not path.exists():
        path = Path(__file__).parent.parent.parent / "config" / relative_path.replace("business/", "business/")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get_llm_client():
    """Return LLM client if API key configured, else None for rule-based fallback."""
    from shared.secrets_provider import get_secret

    provider = os.environ.get("LLM_PROVIDER", "openai")
    if provider == "openai" and get_secret("OPENAI_API_KEY"):
        from openai import OpenAI
        return OpenAI(api_key=get_secret("OPENAI_API_KEY")), os.environ.get("LLM_MODEL", "gpt-4o-mini")
    if provider == "anthropic" and get_secret("ANTHROPIC_API_KEY"):
        import anthropic
        return anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY")), os.environ.get("LLM_MODEL", "claude-3-haiku-20240307")
    return None, None


async def llm_complete(prompt: str, system: str = "") -> str:
    """Call LLM or return rule-based stub."""
    client, model = get_llm_client()
    if client is None:
        return f"[rule-based] Processed: {prompt[:200]}"
    try:
        if hasattr(client, "chat"):
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system or "You are a SpeedFlow platform agent."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
            )
            return resp.choices[0].message.content or ""
        else:
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system or "You are a SpeedFlow platform agent.",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
    except Exception as e:
        logger.warning("LLM call failed, using fallback: %s", e)
        return f"[fallback] {prompt[:200]}"


class AgentState:
    """Shared state store for multi-agent collaboration."""

    def __init__(self):
        self._state: dict[str, Any] = {}
        self._history: list[dict] = []

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value
        self._history.append({"action": "set", "key": key, "value": value})

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def to_dict(self) -> dict:
        return dict(self._state)

    @property
    def history(self) -> list[dict]:
        return list(self._history)
