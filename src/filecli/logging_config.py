"""Application log configuration."""

import logging
from logging.handlers import RotatingFileHandler

from platformdirs import user_log_path


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("filecli")
    if logger.handlers:
        return logger
    log_path = user_log_path("filecli", appauthor=False)
    log_path.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path / "filecli.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
