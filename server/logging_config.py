"""Structured logging configuration with correlation IDs.

Two output modes:

* ``console`` — human-readable coloured output for local development.
* ``json`` — machine-readable JSON lines for production / Docker.

Set ``LOG_FORMAT=json`` (or leave unset for ``console``) and
``LOG_LEVEL=INFO`` (default) to control behaviour.
"""

import contextvars
import logging
import sys

import structlog

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def _add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    cid = correlation_id_var.get("")
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


_common_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_logger_name,
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    _add_correlation_id,
]


def configure_logging(
    level: str = "INFO",
    fmt: str = "console",
) -> None:
    """Set up structlog and stdlib logging for the process."""
    if fmt == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *_common_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for noisy in ("uvicorn", "uvicorn.access", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
