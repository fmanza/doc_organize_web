from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter
from app.core.request_context import RequestIdFilter, bind_request_id, reset_request_id


def _render(record: logging.LogRecord) -> dict[str, object]:
    RequestIdFilter().filter(record)
    result: dict[str, object] = json.loads(JsonFormatter().format(record))
    return result


def test_json_line_with_extra_and_request_id() -> None:
    token = bind_request_id("req-12345678")
    try:
        record = logging.makeLogRecord({"name": "app.x", "levelname": "INFO", "msg": "hola", "run_id": 7})
        line = _render(record)
    finally:
        reset_request_id(token)

    assert line["msg"] == "hola"
    assert line["run_id"] == 7
    assert line["request_id"] == "req-12345678"


def test_no_request_id_outside_requests() -> None:
    line = _render(logging.makeLogRecord({"msg": "fuera"}))

    assert "request_id" not in line
