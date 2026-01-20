"""
Centralized logging configuration.
Prevents duplicate logs while ensuring output appears.
"""

import logging
import sys

# Global registry to track configured loggers
_configured_loggers = set()

def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.
    Ensures logs appear exactly once in terminal.

    Args:
        name (str): Logger name (usually __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure each logger once (prevent duplicates)
    if name in _configured_loggers:
        return logger

    # Clear any existing handlers (cleanup)
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Prevent propagation to root logger (avoid duplicates)
    logger.propagate = False

    # Mark as configured
    _configured_loggers.add(name)

    return logger
