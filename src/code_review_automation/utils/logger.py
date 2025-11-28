"""
Logging Utilities

Centralized logging configuration for the code review tool.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up the main logger for the application.

    Args:
        verbose: Enable debug logging
        log_file: Optional log file path

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("code_reviewer")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"code_reviewer.{name}")


class LoggerMixin:
    """Mixin class to add logging capability to other classes."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        module_name = self.__class__.__module__
        class_name = self.__class__.__name__
        return get_logger(f"{module_name}.{class_name}")


def log_exception(logger: logging.Logger, message: str = "An error occurred") -> None:
    """
    Log exception with full traceback.

    Args:
        logger: Logger instance
        message: Custom error message
    """
    logger.exception(message)


def configure_third_party_loggers() -> None:
    """Configure logging levels for third-party libraries."""
    # Suppress overly verbose third-party logs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("git").setLevel(logging.WARNING)