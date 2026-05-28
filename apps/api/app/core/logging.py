import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict

# Context variable to hold the Correlation ID for the lifetime of a request
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

class StructuredJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "filename": record.filename,
            "line_number": record.lineno,
            "correlation_id": correlation_id_ctx.get()
        }
        
        # Add custom extra parameters if provided
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data.update(record.extra_data)
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    formatter = StructuredJSONFormatter()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Disable propagation or noise from third-party libraries if necessary
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn").handlers = [handler]

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
