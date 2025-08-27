"""
Secure logging configuration for AI Agent Platform.
"""

import json
import logging
import logging.handlers
import sys
import time
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, default=str)


class SecurityFilter(logging.Filter):
    """Filter to prevent sensitive data from being logged."""

    SENSITIVE_KEYWORDS = [
        "password",
        "secret",
        "key",
        "token",
        "auth",
        "credential",
        "private",
        "api_key",
        "jwt",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive information from log records."""
        message = record.getMessage().lower()

        # Check for sensitive keywords
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in message:
                # Mask the sensitive information
                record.msg = "[SENSITIVE DATA FILTERED]"
                record.args = ()
                break

        return True


def setup_logging(
    level: str = "INFO", format_type: str = "json", log_file: Optional[str] = None
):
    """Setup secure logging configuration."""

    # Create logs directory if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatters
    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SecurityFilter())
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SecurityFilter())
        root_logger.addHandler(file_handler)

    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info("🔧 Logging configuration initialized")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with security filtering."""
    logger = logging.getLogger(name)
    return logger
