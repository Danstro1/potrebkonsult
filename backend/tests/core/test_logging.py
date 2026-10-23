import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.LogRecord("app.rag", logging.INFO, __file__, 1, "index_done", None, None)
    record.chunks_count = 130
    record.document_key = "zozpp"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "info"
    assert payload["logger"] == "app.rag"
    assert payload["message"] == "index_done"
    assert payload["chunks_count"] == 130
    assert payload["document_key"] == "zozpp"
    assert "timestamp" in payload
    assert "args" not in payload


def test_json_formatter_keeps_cyrillic_readable() -> None:
    record = logging.LogRecord("app", logging.WARNING, __file__, 1, "Ошибка", None, None)

    assert '"message": "Ошибка"' in JsonFormatter().format(record)
