"""Persist Crawlee scrape job progress to PostgreSQL."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _connection_string() -> str:
    user = os.environ.get("POSTGRES_USER", "admin")
    password = os.environ.get("POSTGRES_PASSWORD", "adminpassword")
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "platform_db")
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def update_scrape_job(job_id: str, **fields) -> None:
    if not job_id or job_id == "unknown":
        return
    allowed = {
        "status", "pages_crawled", "progress_pct", "error_message", "completed_at",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc)

    set_clause = ", ".join(f"{col} = %({col})s" for col in updates)
    updates["job_id"] = job_id

    try:
        import psycopg2

        with psycopg2.connect(_connection_string()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE scrape_jobs SET {set_clause} WHERE job_id = %(job_id)s",
                    updates,
                )
            conn.commit()
    except Exception as exc:
        logger.debug("Job status DB update skipped for %s: %s", job_id, exc)
