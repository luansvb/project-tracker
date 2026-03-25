from decimal import Decimal
import json
import boto3
from boto3.dynamodb.conditions import Key
from config import get_history_table_name, get_region
from utils import decimal_to_native, now_iso


def _to_dynamodb_compatible(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_to_dynamodb_compatible(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_dynamodb_compatible(item) for key, item in value.items()}
    return json.loads(json.dumps(value), parse_float=Decimal)


class HistoryRepository:
    def __init__(self, dynamodb_resource=None, table_name: str | None = None):
        self._dynamodb = dynamodb_resource or boto3.resource('dynamodb', region_name=get_region())
        self._table = self._dynamodb.Table(table_name or get_history_table_name())

    def put_command_event(
        self,
        *,
        tracker_id: str,
        model: str,
        command: str,
        response: str,
        correlation_id: str,
        result: str,
        state_before: dict,
        state_after: dict,
        timestamp: str | None = None,
    ) -> dict:
        event_timestamp = timestamp or now_iso()
        item = {
            'pk': f'TRACKER#{tracker_id}',
            'sk': f'TS#{event_timestamp}#{correlation_id}',
            'tracker_id': tracker_id,
            'timestamp': event_timestamp,
            'event_type': 'COMMAND_EXECUTION',
            'command': command,
            'response': response,
            'result': result,
            'correlation_id': correlation_id,
            'model': model,
            'state_before': _to_dynamodb_compatible(state_before),
            'state_after': _to_dynamodb_compatible(state_after),
        }
        self._table.put_item(Item=item)
        return decimal_to_native(item)

    def list_tracker_history(self, tracker_id: str, limit: int = 20) -> list[dict]:
        safe_limit = max(1, min(int(limit), 100))
        response = self._table.query(
            KeyConditionExpression=Key('pk').eq(f'TRACKER#{tracker_id}'),
            ScanIndexForward=False,
            Limit=safe_limit,
        )
        items = response.get('Items', [])
        return [decimal_to_native(item) for item in items]
