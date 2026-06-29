"""Legacy entry point — delegates to Crawlee worker queue pattern."""

import logging

logger = logging.getLogger(__name__)


def run_loop() -> None:
    logger.warning(
        "Standalone crawlee/scraper.py is deprecated. "
        "Use crawlee-service workers (docker service crawlee-worker)."
    )
    # Minimal poll loop for backward compatibility with shared.runner
    import time
    from shared.job_queue import poll_dynamic_jobs

    while True:
        jobs = poll_dynamic_jobs(timeout=5)
        if jobs:
            logger.info("Received %d jobs — forward to crawlee:jobs queue via platform-api", len(jobs))
        time.sleep(5)
