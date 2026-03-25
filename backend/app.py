import base64
import copy
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TRACKERS_TABLE_NAME = (
    os.getenv("TRACKERS_TABLE_NAME")
    or os.getenv("TRACKER_TABLE_NAME") 
    or os.getenv("TRACKERS_TABLE")
    or os.getenv("TABLE_NAME")
)

HISTORY_TABLE_NAME = os.getenv("HISTORY_TABLE_NAME")

COMMAND_EXECUTED_EVENT_TYPE = "COMMAND_EXECUTED"


def _trackers_table():
    if not TRACKERS_TABLE_NAME:
        raise RuntimeError("Missing TRACKERS_TABLE_NAME / TRACKERS_TABLE / TABLE_NAME")
    return dynamodb.Table(TRACKERS_TABLE_NAME)


def _history_table():
    if not HISTORY_TABLE_NAME:
        raise RuntimeError("Missing HISTORY_TABLE_NAME")
    return dynamodb.Table(HISTORY_TABLE_NAME)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_default(value: Any):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value


def _response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(_to_jsonable(body), ensure_ascii=False, default=_json_default)
    }


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    body = event.get("body")
    if not body:
        return {}

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    return _safe_json_loads(body)


def _method(event: Dict[str, Any]) -> str:
    return (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", "")
        .upper()
    ) or event.get("httpMethod", "").upper()


def _path(event: Dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or ""


def _path_parameters(event: Dict[str, Any]) -> Dict[str, str]:
    return event.get("pathParameters") or {}


def _query_params(event: Dict[str, Any]) -> Dict[str, str]:
    return event.get("queryStringParameters") or {}


def _headers(event: Dict[str, Any]) -> Dict[str, str]:
    raw_headers = event.get("headers") or {}
    return {str(k).lower(): str(v) for k, v in raw_headers.items()}


def _correlation_id(event: Dict[str, Any]) -> str:
    headers = _headers(event)
    return (
        headers.get("x-correlation-id")
        or headers.get("correlation-id")
        or str(uuid.uuid4())
    )


def _normalize_command(command: Optional[str]) -> str:
    if command is None:
        return ""
    normalized = re.sub(r"\s+", "", str(command)).upper()
    return normalized


def _resolve_tracker(tracker_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    table = _trackers_table()
    candidate_keys = [
        {"tracker_id": tracker_id},
        {"pk": f"TRACKER#{tracker_id}", "sk": "STATE"},
    ]

    for key in candidate_keys:
        response = table.get_item(Key=key)
        item = response.get("Item")
        if item:
            return key, item

    return None, None


def _get_tracker_or_raise(tracker_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    key, item = _resolve_tracker(tracker_id)
    if not item or not key:
        raise ValueError(f"Tracker not found: {tracker_id}")
    return key, item


def _query_history(tracker_id: str, limit: int) -> list:
    response = _history_table().query(
        KeyConditionExpression=Key("pk").eq(f"TRACKER#{tracker_id}") & Key("sk").begins_with("TS#"),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get("Items", [])


def _write_history(
    tracker_id: str,
    command: str,
    response_text: str,
    result: str,
    correlation_id: Optional[str],
    model: Optional[str],
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    event_type: str = COMMAND_EXECUTED_EVENT_TYPE
) -> None:
    timestamp = _utc_now_iso()
    history_correlation_id = correlation_id or "system"

    item = {
        "pk": f"TRACKER#{tracker_id}",
        "sk": f"TS#{timestamp}#{history_correlation_id}",
        "tracker_id": tracker_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "command": command,
        "response": response_text,
        "result": result,
        "correlation_id": correlation_id,
        "model": model,
        "state_before": copy.deepcopy(state_before),
        "state_after": copy.deepcopy(state_after),
    }

    _history_table().put_item(Item=item)


def _get_model(tracker: Dict[str, Any]) -> str:
    return (
        str(
            tracker.get("model")
            or tracker.get("model_type")
            or tracker.get("tracker_model")
            or "LT32"
        )
        .strip()
        .upper()
    )


def _logical_relay_on(tracker: Dict[str, Any]) -> bool:
    if "relay_state" in tracker:
        return bool(tracker.get("relay_state"))
    if "relay_enabled" in tracker:
        return bool(tracker.get("relay_enabled"))
    if "relay" in tracker:
        return bool(tracker.get("relay"))
    return False


def _compute_output_active(model: str, relay_on: bool) -> bool:
    normalized_model = model.replace("-", "").replace("_", "")
    if normalized_model == "LT32PRO":
        return relay_on
    return not relay_on


def _apply_mutation(
    tracker_key: Dict[str, Any],
    tracker_before: Dict[str, Any],
    desired_updates: Dict[str, Any]
) -> Tuple[Dict[str, Any], bool]:
    changed_updates = {
        field: value
        for field, value in desired_updates.items()
        if tracker_before.get(field) != value
    }

    if not changed_updates:
        return copy.deepcopy(tracker_before), False

    table = _trackers_table()
    current_version = int(tracker_before.get("version", 0))
    now = _utc_now_iso()

    expression_attribute_names = {}
    expression_attribute_values = {
        ":updated_at": now,
        ":new_version": current_version + 1,
        ":current_version": current_version,
    }

    assignments = ["updated_at = :updated_at", "version = :new_version"]

    for index, (field, value) in enumerate(changed_updates.items(), start=1):
        field_name = f"#f{index}"
        field_value = f":v{index}"
        expression_attribute_names[field_name] = field
        expression_attribute_values[field_value] = value
        assignments.append(f"{field_name} = {field_value}")

    try:
        response = table.update_item(
            Key=tracker_key,
            UpdateExpression="SET " + ", ".join(assignments),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_not_exists(version) OR version = :current_version",
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"], True

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code != "ConditionalCheckFailedException":
            raise

        latest_key, latest_item = _resolve_tracker(
            tracker_before.get("tracker_id")
            or tracker_before.get("id")
            or tracker_before.get("pk", "").replace("TRACKER#", "")
        )

        if latest_item and all(latest_item.get(k) == v for k, v in desired_updates.items()):
            return latest_item, False

        raise RuntimeError("Optimistic locking conflict while updating tracker") from exc


def _build_status_response(tracker: Dict[str, Any]) -> str:
    relay_state = "ON" if _logical_relay_on(tracker) else "OFF"
    sim_state = "ON" if bool(tracker.get("simulation_enabled", False)) else "OFF"

    latitude = tracker.get("latitude", "N/A")
    longitude = tracker.get("longitude", "N/A")
    signal_quality = tracker.get("signal_quality", "N/A")
    battery_voltage = tracker.get("battery_voltage", "N/A")
    model = _get_model(tracker)

    return (
        f"STATUS;MODEL={model};RELAY={relay_state};SIM={sim_state};"
        f"LAT={latitude};LON={longitude};SIG={signal_quality};BAT={battery_voltage}"
    )


def _build_version_response(tracker: Dict[str, Any]) -> str:
    firmware = (
        tracker.get("firmware_version")
        or tracker.get("version_string")
        or "v0.4"
    )
    return f"VERSION:{firmware}"


def _build_param_response(tracker: Dict[str, Any]) -> str:
    sim_state = "ON" if bool(tracker.get("simulation_enabled", False)) else "OFF"
    relay_state = "ON" if _logical_relay_on(tracker) else "OFF"
    return f"PARAM;SIM={sim_state};RELAY={relay_state}"


def _handle_readonly_command(command: str, tracker: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    if command == "STATUS#":
        return _build_status_response(tracker), "OK", copy.deepcopy(tracker)

    if command == "VERSION#":
        return _build_version_response(tracker), "OK", copy.deepcopy(tracker)

    if command == "PARAM#":
        return _build_param_response(tracker), "OK", copy.deepcopy(tracker)

    if command == "RELAY#":
        relay_state = "1" if _logical_relay_on(tracker) else "0"
        return f"RELAY:{relay_state}", "OK", copy.deepcopy(tracker)

    raise ValueError(f"Unsupported readonly command: {command}")


def _handle_relay_command(
    command: str,
    tracker_key: Dict[str, Any],
    tracker: Dict[str, Any]
) -> Tuple[str, str, Dict[str, Any]]:
    desired_on = command == "RELAY,1#"
    current_on = _logical_relay_on(tracker)
    model = _get_model(tracker)

    if current_on == desired_on:
        response_text = f"RELAY;STATE={'ON' if desired_on else 'OFF'};RESULT=NOOP"
        return response_text, "NOOP", copy.deepcopy(tracker)

    desired_updates = {
        "relay_state": desired_on,
        "output_active": _compute_output_active(model, desired_on),
    }

    updated_tracker, changed = _apply_mutation(tracker_key, tracker, desired_updates)

    if not changed:
        response_text = f"RELAY;STATE={'ON' if desired_on else 'OFF'};RESULT=NOOP"
        return response_text, "NOOP", updated_tracker

    response_text = f"RELAY;STATE={'ON' if desired_on else 'OFF'};RESULT=OK"
    return response_text, "OK", updated_tracker


def _handle_sim_command(
    command: str,
    tracker_key: Dict[str, Any],
    tracker: Dict[str, Any]
) -> Tuple[str, str, Dict[str, Any]]:
    desired_enabled = command == "SIM,ON#"
    current_enabled = bool(tracker.get("simulation_enabled", False))

    if current_enabled == desired_enabled:
        response_text = f"SIM;STATE={'ON' if desired_enabled else 'OFF'};RESULT=NOOP"
        return response_text, "NOOP", copy.deepcopy(tracker)

    desired_updates = {
        "simulation_enabled": desired_enabled,
    }

    updated_tracker, changed = _apply_mutation(tracker_key, tracker, desired_updates)

    if not changed:
        response_text = f"SIM;STATE={'ON' if desired_enabled else 'OFF'};RESULT=NOOP"
        return response_text, "NOOP", updated_tracker

    response_text = f"SIM;STATE={'ON' if desired_enabled else 'OFF'};RESULT=OK"
    return response_text, "OK", updated_tracker


def _execute_command(
    tracker_key: Dict[str, Any],
    tracker: Dict[str, Any],
    command: str
) -> Tuple[str, str, Dict[str, Any]]:
    if command in {"STATUS#", "VERSION#", "PARAM#", "RELAY#"}:
        return _handle_readonly_command(command, tracker)

    if command in {"RELAY,0#", "RELAY,1#"}:
        return _handle_relay_command(command, tracker_key, tracker)

    if command in {"SIM,ON#", "SIM,OFF#"}:
        return _handle_sim_command(command, tracker_key, tracker)

    raise ValueError(f"Unsupported command: {command}")


def _handle_health() -> Dict[str, Any]:
    return _response(
        200,
        {
            "status": "ok",
            "service": "project-tracker-command-handler",
        },
    )


def _handle_get_tracker(tracker_id: str) -> Dict[str, Any]:
    try:
        _, tracker = _get_tracker_or_raise(tracker_id)
        return _response(200, tracker)
    except ValueError as exc:
        return _response(404, {"message": str(exc)})
    except Exception as exc:
        logger.exception("get_tracker_failed")
        return _response(500, {"message": "Internal server error", "error": str(exc)})


def _handle_get_history(tracker_id: str, limit: int) -> Dict[str, Any]:
    try:
        _get_tracker_or_raise(tracker_id)
        items = _query_history(tracker_id, limit)
        return _response(
            200,
            {
                "tracker_id": tracker_id,
                "limit": limit,
                "items": items,
            },
        )
    except ValueError as exc:
        return _response(404, {"message": str(exc)})
    except Exception as exc:
        logger.exception("get_history_failed")
        return _response(500, {"message": "Internal server error", "error": str(exc)})


def _handle_post_command(event: Dict[str, Any]) -> Dict[str, Any]:
    correlation_id = _correlation_id(event)

    try:
        payload = _parse_body(event)
        tracker_id = payload.get("tracker_id")
        raw_command = payload.get("command")
        command = _normalize_command(raw_command)

        if not tracker_id:
            return _response(400, {"message": "tracker_id is required"})
        if not command:
            return _response(400, {"message": "command is required"})

        tracker_key, tracker_before = _get_tracker_or_raise(tracker_id)
        state_before = copy.deepcopy(tracker_before)

        response_text, result, state_after = _execute_command(
            tracker_key=tracker_key,
            tracker=tracker_before,
            command=command,
        )

        model = _get_model(tracker_before)

        _write_history(
            tracker_id=tracker_id,
            command=command,
            response_text=response_text,
            result=result,
            correlation_id=correlation_id,
            model=model,
            state_before=state_before,
            state_after=state_after,
            event_type=COMMAND_EXECUTED_EVENT_TYPE,
        )

        logger.info(
            "command_processed | correlation_id=%s | tracker_id=%s | command=%s | result=%s",
            correlation_id,
            tracker_id,
            command,
            result,
        )

        return _response(
            200,
            {
                "tracker_id": tracker_id,
                "command": raw_command,
                "normalized_command": command,
                "response": response_text,
                "result": result,
                "correlation_id": correlation_id,
                "tracker": state_after,
            },
        )

    except ValueError as exc:
        logger.warning(
            "command_validation_failed | correlation_id=%s | error=%s",
            correlation_id,
            str(exc),
        )
        return _response(
            400,
            {
                "message": str(exc),
                "correlation_id": correlation_id,
            },
        )
    except Exception as exc:
        logger.exception(
            "command_failed | correlation_id=%s",
            correlation_id,
        )
        return _response(
            500,
            {
                "message": "Internal server error",
                "error": str(exc),
                "correlation_id": correlation_id,
            },
        )


def lambda_handler(event, context):
    try:
        method = _method(event)
        path = _path(event)
        path_params = _path_parameters(event)
        query_params = _query_params(event)

        if method == "GET" and path == "/health":
            return _handle_health()

        tracker_id = path_params.get("tracker_id")

        if method == "GET" and path.endswith("/history") and tracker_id:
            limit_raw = query_params.get("limit", "20")
            try:
                limit = int(limit_raw)
            except ValueError:
                limit = 20

            if limit <= 0:
                limit = 20
            if limit > 100:
                limit = 100

            return _handle_get_history(tracker_id, limit)

        if method == "GET" and tracker_id:
            return _handle_get_tracker(tracker_id)

        if method == "POST" and path == "/command":
            return _handle_post_command(event)

        return _response(
            404,
            {
                "message": "Route not found",
                "method": method,
                "path": path,
            },
        )

    except Exception as exc:
        logger.exception("unhandled_error")
        return _response(
            500,
            {
                "message": "Internal server error",
                "error": str(exc),
            },
        )
