"""Structured application logging.

Configures the standard library `logging` with a single consistent formatter.
Level is INFO by default and DEBUG when the application runs in debug mode.
"""

import logging.config

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"default": {"format": LOG_FORMAT, "datefmt": DATE_FORMAT}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}


def configure_logging(*, debug: bool = False) -> None:
    config = LOGGING_CONFIG.copy()
    config["root"]["level"] = "DEBUG" if debug else "INFO"
    logging.config.dictConfig(config)