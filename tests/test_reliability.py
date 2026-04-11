"""Tests for ``app.core.reliability`` (ported monolith helpers)."""

from __future__ import annotations

import logging

import pytest
from starlette.requests import Request

from app.core import reliability


def test_incident_code_format() -> None:
    c = reliability.incident_code("REL-GEN")
    assert c.startswith("REL-GEN-")
    assert len(c) > len("REL-GEN-")


def test_safe_user_error() -> None:
    s = reliability.safe_user_error("Something failed", "REL-ABC")
    assert "Something failed" in s
    assert "REL-ABC" in s


def test_ensure_request_id_sets_state() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    req = Request(scope)
    rid = reliability.ensure_request_id(req)
    assert rid
    assert req.state.request_id == rid


def test_emit_reliability_event_no_request(caplog: pytest.LogCaptureFixture) -> None:
    log = logging.getLogger("test_rel")
    with caplog.at_level(logging.INFO, logger="test_rel"):
        reliability.emit_reliability_event(log, "test_event", foo=1)
    assert "[reliability]" in caplog.text
    assert "test_event" in caplog.text
