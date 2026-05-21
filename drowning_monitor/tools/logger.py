"""Simple file logger for the drowning monitor pipeline."""
import json
import logging
import os
from datetime import date, datetime, timezone


LOG_DIR = os.getenv("LOG_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "logs"))


def get_logger(name: str = "drowning_monitor") -> logging.Logger:
    """Return a logger that writes to logs/YYYY-MM-DD.log and to stdout."""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"{date.today().isoformat()}.log")

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def log_search(logger, query: str, raw_count: int, kept_count: int, filtered: list):
    """Log a single search call result."""
    logger.info(f"SEARCH  query={repr(query)}  raw={raw_count}  kept={kept_count}")
    for reason, title, url in filtered:
        logger.debug(f"  FILTERED [{reason}] {title[:60]} | {url[:80]}")


def log_article_date_check(logger, url: str, serpapi_date: str, actual_date, passed: bool):
    """Log the result of fetching an article's actual publish date."""
    actual_str = actual_date.isoformat() if actual_date else "unreadable"
    status = "PASS" if passed else "FAIL (too old)"
    logger.debug(f"  DATE-CHECK {status} | serpapi={repr(serpapi_date)} actual={actual_str} | {url[:80]}")


def log_pipeline_summary(logger, fatal: list, rescued: list, pdf_count: int, email_ok: bool):
    """Log the final pipeline summary."""
    logger.info(
        f"SUMMARY  fatal/potential={len(fatal)}  rescues={len(rescued)}  "
        f"pdfs={pdf_count}  email={'sent' if email_ok else 'FAILED'}"
    )
    for inc in fatal:
        logger.info(f"  [FATAL]  {inc.get('source','')} — {inc.get('title','')[:70]}")
    for inc in rescued:
        logger.info(f"  [RESCUE] {inc.get('source','')} — {inc.get('title','')[:70]}")
