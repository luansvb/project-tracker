import json
import logging

from config import get_log_level

logger = logging.getLogger()
logger.setLevel(get_log_level())


def log_json(level: str, message: str, **fields) -> None:
    payload = {
        'level': level.upper(),
        'message': message,
        **fields,
    }
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(json.dumps(payload, ensure_ascii=False, default=str))
