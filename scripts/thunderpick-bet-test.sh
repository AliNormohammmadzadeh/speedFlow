#!/bin/bash
# End-to-end Thunderpick bet scrape test: proxy → crawl → pipeline → bet extraction report.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

API="${PLATFORM_API_URL:-http://127.0.0.1:8020}"
TARGET_URL="${1:-https://thunderpick.io/esports/dota-2/the-international-2026/9947/team-yandex-vs-team-spirit/2531675}"

export TARGET_URL API ROOT
python3 <<'PY'
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.environ["ROOT"]
API = os.environ["API"]
TARGET_URL = os.environ["TARGET_URL"]

REPORT: dict = {
    "target_url": TARGET_URL,
    "steps": [],
    "proxy": {},
    "job": {},
    "pipeline": {},
    "bets": [],
    "raw_preview": "",
}


def step(name: str, status: str, detail: str = "") -> None:
    REPORT["steps"].append({"step": name, "status": status, "detail": detail})
    mark = "OK" if status == "pass" else ("WARN" if status == "warn" else "FAIL")
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def psql(query: str) -> str:
    env = {**os.environ, "PGPASSWORD": "adminpassword"}
    out = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-p", "5433", "-U", "admin", "-d", "platform_db", "-tAc", query],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return (out.stdout or "").strip()


# --- 1. Proxy connectivity ---
proxy_url = os.environ.get("CRAWLEE_PROXY_URL", "").strip()
if not proxy_url:
    step("Proxy configured", "fail", "CRAWLEE_PROXY_URL missing in .env")
    print(json.dumps(REPORT, indent=2))
    sys.exit(1)

from urllib.parse import urlparse

u = urlparse(proxy_url)
hostport = f"{u.hostname}:{u.port}"
auth = f"{u.username}:{u.password}"
try:
    proc = subprocess.run(
        ["curl", "-sf", "-x", hostport, "-U", auth, "ipinfo.novada.pro"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    info = json.loads(proc.stdout)
    REPORT["proxy"] = {
        "provider": "novada",
        "exit_ip": info.get("ip"),
        "country": info.get("country_code"),
        "city": info.get("city"),
    }
    step("Proxy connectivity", "pass", f"exit IP {info.get('ip')} ({info.get('country_code')})")
except Exception as exc:
    step("Proxy connectivity", "fail", str(exc))
    print(json.dumps(REPORT, indent=2))
    sys.exit(1)

# --- 2. Submit scrape (Pro tenant for proxy) ---
try:
    tenant = http_json("POST", f"{API}/tenants", {
        "name": "Thunderpick Bet Test",
        "plan": "pro",
        "email": "thunderpick-bet-test@demo.local",
    })
    api_key = tenant["api_key"]
    tenant_id = tenant["tenant_id"]
    step("Create Pro tenant", "pass", tenant_id)
except urllib.error.HTTPError as exc:
    step("Create Pro tenant", "fail", exc.read().decode()[:200])
    print(json.dumps(REPORT, indent=2))
    sys.exit(1)

try:
    job_resp = http_json(
        "POST",
        f"{API}/scrape",
        {
            "requirement": (
                "Scrape all betting markets, odds, team names, and match lines from "
                "Thunderpick esports match page via proxy"
            ),
            "url": TARGET_URL,
            "max_pages": 1,
            "crawler_engine": "crawlee_playwright",
            "use_proxy": True,
            "vertical": "gaming_esports",
        },
        headers={"X-API-Key": api_key},
    )
    job_id = job_resp["job_id"]
    plan = job_resp.get("plan") or {}
    REPORT["job"] = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "use_proxy": plan.get("use_proxy"),
        "engine": plan.get("crawler_engine"),
        "urls": plan.get("urls"),
    }
    step(
        "Submit scrape job",
        "pass",
        f"job={job_id} engine={plan.get('crawler_engine')} proxy={plan.get('use_proxy')}",
    )
except urllib.error.HTTPError as exc:
    step("Submit scrape job", "fail", exc.read().decode()[:300])
    print(json.dumps(REPORT, indent=2))
    sys.exit(1)

# --- 3. Wait for crawl ---
status = "queued"
pages = 0
err = ""
for i in range(1, 61):
    row = psql(
        f"SELECT status || '|' || COALESCE(pages_crawled::text,'0') || '|' || COALESCE(error_message,'') "
        f"FROM scrape_jobs WHERE job_id='{job_id}'"
    )
    if row:
        status, pages_s, err = (row + "||").split("|")[:3]
        pages = int(pages_s or 0)
    if status == "completed":
        break
    if status == "failed":
        break
    time.sleep(2)

REPORT["job"]["status"] = status
REPORT["job"]["pages_crawled"] = pages
REPORT["job"]["error_message"] = err or None

if status != "completed" or pages < 1:
    step("Crawlee worker crawl", "fail", f"status={status} pages={pages} err={err[:120] if err else ''}")
    print(json.dumps(REPORT, indent=2))
    sys.exit(1)
step("Crawlee worker crawl", "pass", f"pages={pages}")

# --- 4. Pipeline events ---
source_id = f"{tenant_id}:{job_id}"
raw_topic = f"raw_stream_{tenant_id}"

def load_event_from_kafka(topic: str, timeout_sec: int = 30) -> dict:
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroDeserializer
    from confluent_kafka.serialization import MessageField, SerializationContext
    import uuid as _uuid

    schema_name = "processed_event.avsc" if topic == "processed_stream" else "raw_event.avsc"
    schema = open(os.path.join(ROOT, "schemas/avro", schema_name)).read()
    des = AvroDeserializer(SchemaRegistryClient({"url": "http://127.0.0.1:8081"}), schema)
    consumer = Consumer({
        "bootstrap.servers": "localhost:29092",
        "group.id": f"bet-test-{_uuid.uuid4().hex[:8]}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    payload: dict = {}
    try:
        md = consumer.list_topics(topic, timeout=5)
        if topic not in md.topics:
            return {}
        parts = list(md.topics[topic].partitions.keys())
        consumer.assign([TopicPartition(topic, p, 0) for p in parts])
        deadline = time.time() + timeout_sec
        idle = 0
        while time.time() < deadline:
            msg = consumer.poll(0.5)
            if msg is None:
                idle += 1
                if idle >= 20 and payload:
                    break
                continue
            idle = 0
            if msg.error():
                continue
            val = des(msg.value(), SerializationContext(topic, MessageField.VALUE))
            if isinstance(val, dict) and val.get("source_id") == source_id:
                p = val.get("payload")
                payload = json.loads(p) if isinstance(p, str) else (p or {})
                if topic == "processed_stream":
                    break
    finally:
        consumer.close()
    return payload

event_count = psql(f"SELECT count(*) FROM processed_events WHERE source_id = '{source_id}'")
event_count = int(event_count or 0)
REPORT["pipeline"]["processed_events_count"] = event_count
REPORT["pipeline"]["source_id"] = source_id

payload_json = psql(
    f"SELECT payload::text FROM processed_events WHERE source_id = '{source_id}' "
    f"ORDER BY timestamp DESC LIMIT 1"
)

payload = {}
if payload_json:
    REPORT["pipeline"]["event_source"] = "postgres"
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        payload = {"raw": payload_json}
else:
    for topic in ("processed_stream", raw_topic):
        payload = load_event_from_kafka(topic, timeout_sec=35)
        if payload:
            REPORT["pipeline"]["event_source"] = topic
            event_count = max(event_count, 1)
            break
    if not payload:
        REPORT["pipeline"]["kafka_error"] = "Event not found on processed_stream or dedicated raw topic within timeout"

if payload and payload_json:
    step("Stream processor → processed_events", "pass", f"{event_count} event(s) in Postgres")
elif payload:
    step("Stream processor → processed_events", "pass", f"Event on {REPORT['pipeline'].get('event_source')}")
else:
    step("Stream processor → processed_events", "warn", "No event yet — worker may still be publishing")

# --- 5. Bet extraction from payload ---
text = ""
title = ""
original = payload.get("original") if isinstance(payload.get("original"), dict) else payload
if isinstance(original, dict):
    text = str(original.get("text") or original.get("body") or "")
    title = str(original.get("title") or "")
    betting = original.get("betting") if isinstance(original.get("betting"), dict) else {}
else:
    betting = {}

if betting.get("bets"):
    REPORT["bets"] = betting["bets"][:50]
    REPORT["bets_sample_note"] = f"Showing first 50 of {betting.get('bets_count', len(betting['bets']))} selections"
    REPORT["betting_summary"] = {
        k: betting.get(k)
        for k in ("match_id", "markets_count", "bets_count", "match")
        if betting.get(k) is not None
    }
    step(
        "Bet content extraction",
        "pass",
        f"{betting.get('bets_count', len(REPORT['bets']))} selections across {betting.get('markets_count', '?')} markets",
    )
elif text:
    step("Bet content extraction", "warn", f"Page text captured ({len(text)} chars) but no structured bets in payload")
else:
    log_path = "/tmp/speedflow-crawlee-worker.log"
    if os.path.isfile(log_path):
        with open(log_path) as f:
            tail = f.readlines()[-40:]
        for line in tail:
            if job_id in line and ("done:" in line or "error" in line.lower() or "blocked" in line.lower()):
                REPORT["pipeline"]["worker_log"] = line.strip()

REPORT["page_title"] = title
teams_from_url = re.search(r"/([^/]+)-vs-([^/]+)/", TARGET_URL)
if teams_from_url:
    REPORT["teams"] = [
        teams_from_url.group(1).replace("-", " ").title(),
        teams_from_url.group(2).replace("-", " ").title(),
    ]
REPORT["content_length_chars"] = len(text)

if not REPORT.get("bets") and not any(s["step"] == "Bet content extraction" for s in REPORT["steps"]):
    step("Bet content extraction", "fail", "No betting data in payload")

print()
print("=" * 72)
print("THUNDERPICK BET SCRAPE TEST REPORT")
print("=" * 72)
print(json.dumps(REPORT, indent=2, ensure_ascii=False))
print("=" * 72)
print(f"Portal: http://localhost:8030/ingestion/jobs/{job_id}")

if status == "completed" and pages >= 1 and REPORT.get("bets"):
    sys.exit(0)
sys.exit(1)
PY
