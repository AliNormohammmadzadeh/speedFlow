"""Unified scraper runner - dispatches to the correct scraper type."""

import logging
import sys


def main(scraper_type: str | None = None) -> None:
    scraper_type = scraper_type or (sys.argv[1] if len(sys.argv) > 1 else "rest")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    runners = {
        "rest": "rest.scraper",
        "websocket": "websocket.scraper",
        "crawlee": "crawlee.scraper",
        "selenium": "selenium.scraper",
    }
    module_name = runners.get(scraper_type)
    if not module_name:
        raise ValueError(f"Unknown scraper type: {scraper_type}")

    import importlib
    module = importlib.import_module(module_name)
    module.run_loop()


if __name__ == "__main__":
    main()
