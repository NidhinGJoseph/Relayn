import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Allowlisted fields only: never serialize request objects or exception messages."""

    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        for key in ("dependency", "status_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)
