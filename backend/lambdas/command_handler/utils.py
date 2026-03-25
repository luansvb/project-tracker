from datetime import datetime, timezone
from decimal import Decimal


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decimal_to_native(value):
    if isinstance(value, list):
        return [decimal_to_native(item) for item in value]
    if isinstance(value, dict):
        return {key: decimal_to_native(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value
