"""
Centralized logging configuration for the trade-bot application.

This module provides a consistent logging setup across the entire application,
using the standard Python logging module with appropriate formatters and handlers.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _resolve_log_dir() -> Path:
    """
    Resolve the directory log files are written to.

    Order of precedence:
      1. ``LOG_DIR`` environment variable (absolute or relative path) — lets the
         VM / systemd unit pin a deterministic location regardless of where the
         process is launched from.
      2. ``<repo root>/logs`` — derived from this file's location, so it does not
         depend on the current working directory.
    """
    env_dir = os.environ.get("LOG_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path(__file__).resolve().parent.parent.parent / "logs"


def setup_logger(name: str, log_level=logging.INFO, rotate: bool = True):
    """
    Set up a logger with both console and file handlers.

    Args:
        name (str): Logger name. The log file is named ``<last segment>.log``,
            e.g. ``setup_logger("worker")`` -> ``worker.log``.
        log_level: Logging level (default: logging.INFO)
        rotate (bool): When True (default), use a size-based RotatingFileHandler.
            Set False for loggers that are written to from multiple processes
            sharing the same file (e.g. every ``worker`` subprocess writes to
            ``worker.log``) — rotation across processes races and can leave the
            active file orphaned/blank, so those use a plain append handler.

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.propagate = False  # Prevent propagation to parent loggers to avoid duplicate logs

    # Only add handlers if they don't already exist
    if not logger.handlers:
        # Create logs directory if it doesn't exist (parents=True: never fail if
        # an intermediate dir is missing on a fresh VM).
        log_dir = _resolve_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler
        log_file = log_dir / f"{name.split('.')[-1]}.log"
        if rotate:
            file_handler: logging.Handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
            )
        else:
            # Append mode, no rotation — safe for multiple processes sharing one file.
            file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Make the resolved path discoverable on the VM — printed once per logger
        # to stderr so it shows up even before any log line is emitted.
        print(f"[logger] '{name}' -> {log_file}", file=sys.stderr, flush=True)

    return logger
