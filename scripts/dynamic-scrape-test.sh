#!/bin/bash
# Dynamic scrape matrix — one planner, profile-driven extraction on 4 diverse sites.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

API="${PLATFORM_API_URL:-http://127.0.0.1:8020}"

export ROOT API
python3 <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.environ["ROOT"]
API = os.environ["API"]

CASES = [
    {
        "name": "example_static",
        "plan": "starter",
        "requirement": "Extract the full page text and main heading from the example homepage",
        "url": "https://example.com",
        "max_pages": 1,
        "expect_strategy": "full_text",
        "min_records": 0,
    },
    {
        "name": "books_dom",
        "plan": "starter",
        "requirement": "Extract book titles and prices from the bookstore catalog page",
        "url": "https://books.toscrape.com/",
        "max_pages": 1,
        "expect_profile": "books_listing",
        "min_records": 5,
    },
    {
        "name": "hn_dom",
        "plan": "starter",
        "requirement": "Extract story titles and scores from the Hacker News front page",
        "url": "https://news.ycombinator.com/",
        "max_pages": 1,
        "expect_profile": "news_listing",
        "min_records": 5,
    },
    {
        "name": "betting_network_api",
        "plan": "pro",
        "requirement": "Extract betting markets, odds, and match info from this esports match page via proxy",
        "url": "https://thunderpick.io/esports/dota-2/the-international-2026/9947/team-yandex-vs-team-spirit/2531675",
        "max_pages": 1,
        "use_proxy": True,
        "expect_strategy": "network_api",
        "min_records": 10,
    },
]

results: list[dict] = []


def http_json(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def psql(query):
    env = {**os.environ, "PGPASSWORD": "adminpassword"}
    out = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-p", "5433", "-U", "admin", "-d", "platform_db", "-tAc", query],
        capture_output=True, text=True, env=env, check=False,
    )
    return (out.stdout or "").strip()


def fetch_kafka_payload(source_id: str, tenant_id: str) -> dict:
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroDeserializer
    from confluent_kafka.serialization import MessageField, SerializationContext
    import uuid as _uuid

    for topic, schema_file in (
        ("processed_stream", "processed_event.avsc"),
        (f"raw_stream_{tenant_id}", "raw_event.avsc"),
    ):
        schema = open(os.path.join(ROOT, "schemas/avro", schema_file)).read()
        des = AvroDeserializer(SchemaRegistryClient({"url": "http://127.0.0.1:8081"}), schema)
        consumer = Consumer({
            "bootstrap.servers": "localhost:29092",
            "group.id": f"dyn-{ _uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        try:
            md = consumer.list_topics(topic, timeout=5)
            if topic not in md.topics:
                continue
            parts = list(md.topics[topic].partitions.keys())
            consumer.assign([TopicPartition(topic, p, 0) for p in parts])
            deadline = time.time() + 25
            while time.time() < deadline:
                msg = consumer.poll(0.5)
                if msg is None or msg.error():
                    continue
                val = des(msg.value(), SerializationContext(topic, MessageField.VALUE))
                if isinstance(val, dict) and val.get("source_id") == source_id:
                    p = val.get("payload")
                    return json.loads(p) if isinstance(p, str) else (p or {})
        finally:
            consumer.close()
    return {}


print("=" * 72)
print("DYNAMIC SCRAPE MATRIX")
print("=" * 72)

for case in CASES:
    row = {"case": case["name"], "status": "fail", "detail": ""}
    print(f"\n--- {case['name']} ---")
    try:
        tenant = http_json("POST", f"{API}/tenants", {
            "name": f"Dynamic Test {case['name']}",
            "plan": case["plan"],
            "email": f"dyn-{case['name']}@demo.local",
        })
        body = {
            "requirement": case["requirement"],
            "url": case["url"],
            "max_pages": case["max_pages"],
            "crawler_engine": "auto",
        }
        if case.get("use_proxy"):
            body["use_proxy"] = True

        job_resp = http_json("POST", f"{API}/scrape", body, headers={"X-API-Key": tenant["api_key"]})
        job_id = job_resp["job_id"]
        plan = job_resp.get("plan") or {}
        row["plan"] = {
            "engine": plan.get("crawler_engine"),
            "strategy": plan.get("extraction_strategy"),
            "profile": plan.get("extraction_profile"),
            "use_proxy": plan.get("use_proxy"),
        }

        status = "queued"
        for _ in range(60):
            status = psql(f"SELECT status FROM scrape_jobs WHERE job_id='{job_id}'") or status
            if status in ("completed", "failed"):
                break
            time.sleep(2)

        if status != "completed":
            err = psql(f"SELECT error_message FROM scrape_jobs WHERE job_id='{job_id}'")
            row["detail"] = f"job {status}: {err}"
            results.append(row)
            print("FAIL", row["detail"])
            continue

        source_id = f"{tenant['tenant_id']}:{job_id}"
        payload = fetch_kafka_payload(source_id, tenant["tenant_id"])
        original = payload.get("original") if isinstance(payload.get("original"), dict) else payload
        extracted = (original or {}).get("extracted") or {}
        records = extracted.get("records") or []
        row["extracted"] = {
            "strategy": extracted.get("strategy"),
            "profile": extracted.get("profile"),
            "records_count": extracted.get("stats", {}).get("records_count", len(records)),
            "sample": records[:3],
        }

        ok = len(records) >= case.get("min_records", 1)
        if case.get("expect_profile") and plan.get("extraction_profile") != case["expect_profile"]:
            ok = False
            row["detail"] += f" profile={plan.get('extraction_profile')} expected {case['expect_profile']}"
        if case.get("expect_strategy") and extracted.get("strategy") != case["expect_strategy"]:
            if not (case["expect_strategy"] == "full_text" and len(records) == 0 and original.get("text")):
                ok = False
                row["detail"] += f" strategy={extracted.get('strategy')} expected {case['expect_strategy']}"

        if ok or (case["name"] == "example_static" and original.get("text")):
            row["status"] = "pass"
            row["detail"] = f"records={len(records)} engine={plan.get('crawler_engine')}"
        else:
            row["detail"] = row["detail"] or f"records={len(records)} below min {case.get('min_records')}"

        print(row["status"].upper(), row["detail"])
        if records[:1]:
            print("  sample:", json.dumps(records[0], ensure_ascii=False)[:120])
    except Exception as exc:
        row["detail"] = str(exc)[:200]
        print("FAIL", row["detail"])
    results.append(row)

passed = sum(1 for r in results if r["status"] == "pass")
print("\n" + "=" * 72)
print(f"SUMMARY: {passed}/{len(results)} passed")
print(json.dumps(results, indent=2, ensure_ascii=False))
print("=" * 72)
sys.exit(0 if passed == len(results) else 1)
PY
