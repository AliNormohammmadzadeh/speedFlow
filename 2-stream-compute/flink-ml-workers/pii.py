"""PII scanning + redaction per config/security/compliance.yaml.

Applied in the stream processor before events are persisted to Postgres/OpenSearch
so downstream stores never receive raw PII (compliance: redact_fields +
block_on_pii_detected).
"""

import os
import re

REDACTION = "[REDACTED]"

# Field names to always redact (from compliance.yaml pii_handling.redact_fields).
_DEFAULT_FIELDS = os.environ.get("REDACT_FIELDS", "email,phone,ssn,credit_card").split(",")
REDACT_FIELDS = {f.strip().lower() for f in _DEFAULT_FIELDS if f.strip()}

PII_ENABLED = os.environ.get("PII_REDACTION_ENABLED", "true").lower() in ("1", "true", "yes")
BLOCK_ON_PII = os.environ.get("PII_BLOCK_ON_DETECT", "false").lower() in ("1", "true", "yes")

# Value patterns for content-based detection/redaction.
PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,2}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}\b"),
}


def _redact_str(value: str, counter: dict) -> str:
    out = value
    for name, pat in PATTERNS.items():
        new, n = pat.subn(REDACTION, out)
        if n:
            counter["count"] += n
            out = new
    return out


def redact(obj, counter: dict | None = None):
    """Recursively redact PII in a dict/list/str. Returns (redacted_obj, count)."""
    if counter is None:
        counter = {"count": 0}
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in REDACT_FIELDS:
                result[k] = REDACTION
                counter["count"] += 1
            else:
                result[k] = redact(v, counter)[0]
        return result, counter["count"]
    if isinstance(obj, list):
        return [redact(v, counter)[0] for v in obj], counter["count"]
    if isinstance(obj, str):
        return _redact_str(obj, counter), counter["count"]
    return obj, counter["count"]


def scan(obj) -> bool:
    """Return True if any PII is detected (does not mutate)."""
    _, count = redact(obj)
    return count > 0
