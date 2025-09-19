import logging
from logging.config import dictConfig
from typing import Any, Dict

def setup_logging(*, level: str = "INFO", include_access: bool = True, json: bool = False) -> None:
    """
    Configure logging for the app and uvicorn.
    - level: base level the app logger
    - include_access: whether to enable uvicorn.access (HTTP access logs)
    - json: optional JSON logging (requires python-json-logger if True)
    """
    # Base text format
    default_fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    formatters: Dict[str, Any] = {
        "default": {
            "format": default_fmt,
            "datefmt": date_fmt,
        },
        # Uvicorn pretty formatters
        "uvicorn_default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s %(message)s",
            "datefmt": date_fmt,
        },
        "uvicorn_access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": "%(levelprefix)s %(client_addr)s - \"%(request_line)s\" %(status_code)s",
        },
    }

    # Optional JSON formatter
    if json:
        formatters["json"] = {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json" if json else "default",
            },
            "uvicorn": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "uvicorn_default",
            },
            "uvicorn_access": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "uvicorn_access",
            },
        },
        "loggers": {
            # app modules use this (via logging.getLogger(__name__))
            "": {  # root logger
                "handlers": ["console"],
                "level": level.upper(),
            },
            # Uvicorn internals
            "uvicorn": {
                "handlers": ["uvicorn"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["uvicorn"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["uvicorn_access"],
                "level": "INFO",
                "propagate": False,
                **({} if include_access else {"level": "CRITICAL"}),  # mutes access logs
            },
        },
    })
