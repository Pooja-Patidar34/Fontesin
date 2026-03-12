import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):

    def format(self, record):

        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "logger": record.name
        }

        if hasattr(record, "tenant"):
            log_record["tenant"] = record.tenant

        if hasattr(record, "endpoint"):
            log_record["endpoint"] = record.endpoint

        if hasattr(record, "actor"):
            log_record["actor"] = record.actor

        if hasattr(record, "metadata"):
            log_record["metadata"] = record.metadata

        return json.dumps(log_record, default=str)