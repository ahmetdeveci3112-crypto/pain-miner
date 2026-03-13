# utils/logger.py

import logging
import os
from datetime import datetime


def setup_logger(name="pain-miner"):
    """Configure and return a logger instance."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    os.makedirs("logs", exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logger.level)

    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f"logs/pain_miner_{today}.log")
    file_handler.setLevel(logger.level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
