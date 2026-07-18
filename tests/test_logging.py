"""Tests for structured logging configuration and correlation IDs."""

import json
import logging
import sys
from io import StringIO

import structlog

from server.logging_config import (
    configure_logging,
    correlation_id_var,
    _add_correlation_id,
)


def test_configure_logging_console_mode(capfd):
    configure_logging(level="DEBUG", fmt="console")

    logger = structlog.get_logger("test_console")
    logger.info("hello_console", value=42)

    captured = capfd.readouterr()
    assert "hello_console" in captured.err
    assert "value=42" in captured.err


def test_configure_logging_json_mode(capfd):
    configure_logging(level="INFO", fmt="json")

    logger = structlog.get_logger("test_json")
    logger.info("hello_json", value=99)

    captured = capfd.readouterr()
    lines = [line for line in captured.err.strip().splitlines() if line.strip()]
    assert lines
    parsed = json.loads(lines[-1])
    assert parsed["event"] == "hello_json"
    assert parsed["value"] == 99


def test_correlation_id_var_defaults_to_empty():
    token = correlation_id_var.set("")
    try:
        assert correlation_id_var.get("") == ""
    finally:
        correlation_id_var.reset(token)


def test_correlation_id_var_is_context_scoped():
    token_outer = correlation_id_var.set("outer")

    class FakeLogger:
        pass

    class FakeMethod:
        pass

    event_dict: dict = {}

    token_inner = correlation_id_var.set("inner")
    try:
        result = _add_correlation_id(FakeLogger(), FakeMethod(), event_dict)
        assert result["correlation_id"] == "inner"
    finally:
        correlation_id_var.reset(token_inner)
        correlation_id_var.reset(token_outer)


def test_add_correlation_id_omits_when_empty():
    token = correlation_id_var.set("")
    try:
        event_dict: dict = {}
        result = _add_correlation_id(None, None, event_dict)
        assert "correlation_id" not in result
    finally:
        correlation_id_var.reset(token)


def test_configure_logging_quietens_noisy_loggers():
    configure_logging(level="WARNING", fmt="console")

    for name in ("uvicorn", "uvicorn.access", "httpcore", "httpx"):
        assert logging.getLogger(name).level >= logging.WARNING
