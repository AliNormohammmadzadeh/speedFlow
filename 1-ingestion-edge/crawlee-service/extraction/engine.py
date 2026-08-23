"""Runtime extraction — DOM, network JSON, and unified payload shape."""

from __future__ import annotations

import fnmatch
import json
import re
from typing import Any
from urllib.parse import urlparse


def is_bot_block(title: str, body: str) -> bool:
    title_l = (title or "").lower()
    body_l = (body or "").lower()
    if "you have been blocked" in body_l:
        return True
    return any(token in title_l for token in ("cloudflare", "just a moment", "attention required"))


def url_id_from_path(url: str, mode: str = "last_numeric") -> str | None:
    if mode == "last_numeric":
        match = re.search(r"/(\d+)/?$", urlparse(url).path)
        return match.group(1) if match else None
    return None


def url_matches_pattern(url: str, pattern: str) -> bool:
    return fnmatch.fnmatch(url, pattern) or fnmatch.fnmatch(urlparse(url).path, pattern)


def get_json_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _first_present(item: dict[str, Any], keys: str) -> Any:
    for key in keys.split("|"):
        key = key.strip()
        if key in item and item[key] is not None:
            return item[key]
    return None


def dom_fields_to_records(fields: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn {field: [v1,v2]} selector output into list of row dicts."""
    list_fields = {k: v for k, v in fields.items() if isinstance(v, list)}
    if not list_fields:
        return [{k: v for k, v in fields.items() if not str(k).startswith("_")}]

    max_len = max(len(v) for v in list_fields.values())
    records: list[dict[str, Any]] = []
    for i in range(max_len):
        row: dict[str, Any] = {}
        for key, values in list_fields.items():
            row[key] = values[i] if i < len(values) else None
        for key, val in fields.items():
            if key not in list_fields:
                row[key] = val
        records.append(row)
    return records


def apply_json_rules(
    rules: list[dict[str, Any]],
    api_responses: list[tuple[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    entities: dict[str, Any] = {}

    for rule in rules:
        rule_id = rule.get("id", "record")
        for url, body in api_responses:
            if not url_matches_pattern(url, rule.get("url_match", "*")):
                continue
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("ok") is False:
                continue

            if rule.get("store_entity"):
                entity_key = str(rule["store_entity"])
                data = get_json_path(parsed, rule.get("path", "data")) if rule.get("path") else parsed
                if isinstance(data, dict):
                    pick = rule.get("pick")
                    if pick:
                        entities[entity_key] = {k: data.get(k) for k in pick if k in data}
                        if "competition" in pick and isinstance(data.get("competition"), dict):
                            entities[entity_key]["competition"] = data["competition"].get("name")
                    else:
                        entities[entity_key] = data
                continue

            items = get_json_path(parsed, rule.get("records_path", "data"))
            if not isinstance(items, list):
                continue

            field_map = rule.get("map") or {}
            expand = rule.get("expand") or {}

            for item in items:
                if not isinstance(item, dict):
                    continue
                base = {out: item.get(src) for out, src in field_map.items()}

                if expand.get("array") and isinstance(item.get(expand["array"]), list):
                    expand_fields = expand.get("fields") or {}
                    for sub in item[expand["array"]]:
                        if not isinstance(sub, dict):
                            continue
                        row = dict(base)
                        for out, src in expand_fields.items():
                            row[out] = _first_present(sub, src) if "|" in str(src) else sub.get(src)
                        row["_rule"] = rule_id
                        records.append(row)
                else:
                    base["_rule"] = rule_id
                    records.append(base)

    return records, entities


def build_extracted_payload(
    job: dict[str, Any],
    *,
    dom_fields: dict[str, Any] | None = None,
    title: str | None = None,
    text: str | None = None,
    api_responses: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    strategy = job.get("extraction_strategy") or job.get("extract_mode") or "full_text"
    profile = job.get("extraction_profile")
    records: list[dict[str, Any]] = []
    entities: dict[str, Any] = {}

    if strategy == "network_api" and api_responses:
        rules = job.get("json_rules") or []
        records, entities = apply_json_rules(rules, api_responses)
    elif dom_fields:
        records = dom_fields_to_records(dom_fields)

    return {
        "strategy": strategy,
        "profile": profile,
        "records": records[:500],
        "entities": entities,
        "stats": {
            "records_count": len(records),
            "sources": sorted({urlparse(u).path for u, _ in (api_responses or [])})[:20],
        },
        "page": {
            "title": title,
            "text_length": len(text or ""),
        },
    }


def finalize_page_payload(
    job: dict[str, Any],
    url: str,
    *,
    title: str = "",
    text: str = "",
    dom_fields: dict[str, Any] | None = None,
    api_responses: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Unified page payload for Kafka — raw capture + structured extracted block."""
    payload: dict[str, Any] = {"title": title, "text": text[:50000], "url": url}
    if dom_fields:
        payload["fields"] = dom_fields
    payload["extracted"] = build_extracted_payload(
        job,
        dom_fields=dom_fields,
        title=title,
        text=text,
        api_responses=api_responses,
    )
    return payload


def network_capture_config(job: dict[str, Any]) -> dict[str, Any]:
    return dict(job.get("network_capture") or {})


def should_capture_url(url: str, cfg: dict[str, Any]) -> bool:
    includes = cfg.get("url_include") or ["/api/"]
    return any(part in url for part in includes)


def playwright_crawler_extras(job: dict[str, Any]) -> dict[str, Any]:
    cfg = network_capture_config(job)
    extras: dict[str, Any] = {}
    if cfg.get("ignore_http_status"):
        extras["ignore_http_error_status_codes"] = list(cfg["ignore_http_status"])
    if cfg.get("max_request_retries"):
        extras["max_request_retries"] = int(cfg["max_request_retries"])
    return extras


def wait_config_for_url(page_url: str, job: dict[str, Any]) -> dict[str, Any]:
    cfg = network_capture_config(job)
    url_id = None
    if cfg.get("url_id_from_path"):
        url_id = url_id_from_path(page_url, cfg["url_id_from_path"])
    return {
        "wait_ms": int(cfg.get("wait_ms", 3000)),
        "retries": int(cfg.get("retries", 1)),
        "min_body_chars": int(cfg.get("min_body_chars", 200)),
        "url_id": url_id,
        "wait_for_contains": list(cfg.get("wait_for_url_contains") or []),
    }


def capture_satisfied(page_url: str, api_responses: list[tuple[str, str]], wait_cfg: dict[str, Any]) -> bool:
    if not wait_cfg.get("wait_for_contains"):
        return len((api_responses or [])) > 0
    url_id = wait_cfg.get("url_id")
    for needle in wait_cfg["wait_for_contains"]:
        target = needle.replace("{url_id}", url_id or "")
        if any(target in u for u, _ in api_responses):
            return True
    return False
