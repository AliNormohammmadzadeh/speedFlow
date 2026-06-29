"""WebSocket scraper - subscribes to live streams."""

import asyncio
import json
import logging
from pathlib import Path

import websockets
import yaml

from shared.job_queue import merge_sources, poll_dynamic_jobs
from shared.kafka_client import build_raw_event, create_producer, publish_event

logger = logging.getLogger(__name__)


def load_config() -> list[dict]:
    config_path = Path(__file__).parent.parent / "config" / "websocket.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    return [s for s in data.get("sources", []) if s.get("enabled", True)]


async def listen_source(source: dict, producer) -> None:
    url = source["url"]
    while True:
        try:
            async with websockets.connect(url) as ws:
                logger.info("Connected to WebSocket: %s", source["id"])
                async for message in ws:
                    try:
                        payload = json.loads(message)
                    except json.JSONDecodeError:
                        payload = {"raw": message[:5000]}
                    event = build_raw_event(
                        source_id=source["id"],
                        source_type="websocket",
                        vertical=source.get("vertical", "unknown"),
                        event_type=source.get("event_type", "ws_message"),
                        payload=payload,
                        url=url,
                        value_score=source.get("value_score"),
                    )
                    publish_event(producer, event)
        except Exception as e:
            logger.error("WebSocket error for %s: %s — reconnecting in 5s", source["id"], e)
            await asyncio.sleep(5)


async def run_async() -> None:
    logging.basicConfig(level=logging.INFO)
    producer = create_producer()
    static = load_config()
    dynamic = poll_dynamic_jobs(timeout=0)
    sources = merge_sources(static, dynamic)
    if not sources:
        logger.warning("No WebSocket sources configured")
        while True:
            await asyncio.sleep(60)
    await asyncio.gather(*(listen_source(s, producer) for s in sources))


def run_loop() -> None:
    asyncio.run(run_async())
