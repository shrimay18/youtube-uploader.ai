"""Central logging config.

One place to configure levels/format so the CLI, the web API, and (later) the
hosted backend all log the same way. Level is env-driven (TM_LOG_LEVEL), so you
flip verbosity in prod without code changes. Import and call configure_logging()
once at process start.
"""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    """Idempotently configure the root logger. Honors TM_LOG_LEVEL (default INFO)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = (level or os.environ.get("TM_LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, lvl, logging.INFO))
    # Quiet noisy libraries unless we're explicitly debugging.
    for noisy in ("werkzeug", "urllib3", "httpx", "googleapiclient"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
