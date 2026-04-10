"""Centralized logging configuration for Gaffer's Clipboard.

This module initializes application logging with three handlers:
1. A rotating main log file for INFO and higher messages.
2. A rotating debug log file for DEBUG, WARNING, ERROR, and CRITICAL
   messages (excluding INFO).
3. A console stream handler for INFO and higher runtime visibility.

The configuration is intended to be applied once during startup so all
application modules inherit a consistent root logger setup.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging():
    """Configure root logging handlers and startup log metadata.

    Creates the logs directory if needed, wires rotating file handlers and a
    console handler onto the root logger, and writes a startup banner showing
    log file locations.

    Returns:
        None

    Notes:
        This function should be called once at application startup.
    """
    project_root = Path(__file__).parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "gaffers_clipboard.log"
    debug_log_file = log_dir / "gaffers_clipboard_debug.log"

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Main log handler (INFO and above)
    main_handler = logging.handlers.RotatingFileHandler(
        filename=log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    # Debug log handler (DEBUG, WARNING, ERROR, CRITICAL - no INFO)
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=debug_log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(lambda record: record.levelno != logging.INFO)
    debug_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(main_handler)
    root_logger.addHandler(debug_handler)
    root_logger.addHandler(console_handler)

    logging.info("==========================================")
    logging.info("   Gaffer's Clipboard - Started")
    logging.info(f"   Log file: {log_file}")
    logging.info(f"   Debug log file: {debug_log_file}")
    logging.info("==========================================")
