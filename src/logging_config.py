import logging
import logging.handlers
import sys
from pathlib import Path

def setup_logging():
    project_root = Path(__file__).parent.parent
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "gaffers_clipboard.log"
    debug_log_file = log_dir / "gaffers_clipboard_debug.log"  # New debug log file
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    handlers = [
        logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(  # New handler for debug logs
            filename=debug_log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
    ]
    
    logging.basicConfig(
        level=logging.INFO,  # Main log level
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )
    
    # Create a separate logger for debug logs
    debug_logger = logging.getLogger()
    debug_logger.setLevel(logging.DEBUG)  # Set to DEBUG level for the debug log file
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=debug_log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    debug_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    debug_logger.addHandler(debug_handler)

    logging.info("==========================================")
    logging.info("   Gaffer's Clipboard - Started")
    logging.info(f"   Log file: {log_file}")
    logging.info(f"   Debug log file: {debug_log_file}")
    logging.info("==========================================")