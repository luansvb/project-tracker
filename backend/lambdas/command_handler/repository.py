import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from config import get_region, get_table_name
from exceptions import ConcurrencyConflictError, TrackerNotFoundError
from utils import decimal_to_native, now_iso


class TrackerRepository:
    def __init__(self, dynamodb_resource=None, table_name: str | None = None):
        self._dynamodb = dynamodb_resource or boto3.resource("dynamodb", region_name=get_region())
        self._table = self._dynamodb.Table(table_name or get_table_name())

    def get_tracker(self, tracker_id: str) -> dict:
        response = self._table.get_item(Key={"tracker_id": tracker_id})
        item = response.get("Item")
        if not item:
            raise TrackerNotFoundError(f"Tracker '{tracker_id}' não encontrado.")
        return decimal_to_native(item)

    def update_relay_state(self, tracker: dict, desired_state: int, normalized_command: str) -> None:
        current_version = int(tracker.get("version", 0))
        current_timestamp = now_iso()

        try:
            self._table.update_item(
                Key={"tracker_id": tracker["tracker_id"]},
                UpdateExpression=(
                    "SET relay_state = :relay_state, "
                    "last_command = :last_command, "
                    "last_command_at = :last_command_at, "
                    "updated_at = :updated_at, "
                    "#version = :next_version"
                ),
                ConditionExpression="attribute_exists(tracker_id) AND (#version = :current_version OR attribute_not_exists(#version))",
                ExpressionAttributeNames={
                    "#version": "version",
                },
                ExpressionAttributeValues={
                    ":relay_state": desired_state,
                    ":last_command": normalized_command,
                    ":last_command_at": current_timestamp,
                    ":updated_at": current_timestamp,
                    ":current_version": current_version,
                    ":next_version": current_version + 1,
                },
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                raise ConcurrencyConflictError(
                    f"Conflito de atualização no tracker '{tracker['tracker_id']}'. Recarregue o estado e tente novamente."
                ) from exc
            raise


class TelemetryRepository:
    def __init__(self, dynamodb_resource=None, table_name: str | None = None):
        self._dynamodb = dynamodb_resource or boto3.resource("dynamodb", region_name=get_region())
        resolved_table_name = table_name or os.environ.get("TELEMETRY_TABLE_NAME")
        if not resolved_table_name:
            raise ValueError("Variável de ambiente TELEMETRY_TABLE_NAME não configurada.")
        self._table = self._dynamodb.Table(resolved_table_name)

    def list_positions(
        self,
        tracker_id: str,
        start_iso: str,
        end_iso: str,
        limit: int = 1000,
    ) -> list[dict]:
        response = self._table.query(
            KeyConditionExpression=Key("tracker_id").eq(tracker_id) & Key("recorded_at").between(start_iso, end_iso),
            ScanIndexForward=True,
            Limit=limit,
        )
        return [decimal_to_native(item) for item in response.get("Items", [])]
