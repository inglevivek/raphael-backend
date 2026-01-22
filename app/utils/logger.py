"""
Centralized logging configuration with optional Rich support.
"""
import logging
import sys
import os

# Global registry to track configured loggers
_configured_loggers = set()

# Check if Rich should be used (default: enabled in TTY)
USE_RICH = os.getenv('USE_RICH_LOGGING', 'auto').lower()

if USE_RICH == 'auto':
    USE_RICH = sys.stdout.isatty()
elif USE_RICH in ('true', '1', 'yes'):
    USE_RICH = True
else:
    USE_RICH = False


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.
    Uses Rich handler if available and enabled, otherwise standard logging.

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

    # Try to use Rich handler if available and enabled
    if USE_RICH:
        try:
            from rich.logging import RichHandler

            handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_level=True,
                show_path=True,
                markup=True
            )

            # Simple format for Rich (it adds its own formatting)
            formatter = logging.Formatter('%(message)s')

        except ImportError:
            # Rich not installed, fall back to standard handler
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    else:
        # Standard console handler
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Prevent propagation to root logger (avoid duplicates)
    logger.propagate = False

    # Mark as configured
    _configured_loggers.add(name)

    return logger