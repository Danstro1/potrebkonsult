"""Структурированное JSON-логирование."""

import json
import logging
from datetime import UTC, datetime

# Атрибуты, которые есть у любой LogRecord; всё остальное пришло через extra=.
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys() | {"message", "asctime"}
)


class JsonFormatter(logging.Formatter):
    """Форматирует запись лога в одну JSON-строку вместе с полями из ``extra``."""

    def format(self, record: logging.LogRecord) -> str:
        """Возвращает запись лога в виде JSON.

        Args:
            record: Запись лога.

        Returns:
            JSON-строка с timestamp, level, logger, message и дополнительными полями.
        """
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {key: value for key, value in record.__dict__.items() if key not in _STANDARD_ATTRS}
        )
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Настраивает корневой логгер на вывод JSON в stderr.

    Args:
        level: Минимальный уровень логирования.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # httpx логирует каждый запрос на уровне info — при индексации это сотни строк.
    logging.getLogger("httpx").setLevel(logging.WARNING)
