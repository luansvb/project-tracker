import copy
import json
import logging
import os
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TRACKERS_TABLE_NAME = (
    os.getenv("TRACKERS_TABLE_NAME")
    or os.getenv("TRACKERS_TABLE")
    or os.getenv("TABLE_NAME")
)

HISTORY_TABLE_NAME = os.getenv("HISTORY_TABLE_NAME")

SIMULATION_EVENT_TYPE = "SIMULATION_TICK"
SIMULATION_COMMAND_NAME = "SIMULATION"
SIMULATION_RESPONSE_TEXT = "SIMULATION_TICK"
SIMULATION_RESULT = "SUCCESS"


def _trackers_table():
    if not TRACKERS_TABLE_NAME:
        raise RuntimeError("Missing TRACKERS_TABLE_NAME / TRACKERS_TABLE / TABLE_NAME")
    return dynamodb.Table(TRACKERS_TABLE_NAME)


def _history_table():
    if not HISTORY_TABLE_NAME:
        raise RuntimeError("Missing HISTORY_TABLE_NAME")
    return dynamodb.Table(HISTORY_TABLE_NAME)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _to_decimal(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return [_to_decimal(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_decimal(item) for key, item in value.items()}
    return value


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _json_default(value: Any):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(_to_jsonable(body), ensure_ascii=False, default=_json_default)
    }


def _tracker_key(item: Dict[str, Any]) -> Dict[str, Any]:
    if "pk" in item and "sk" in item:
        return {
            "pk": item["pk"],
            "sk": item["sk"],
        }

    if "tracker_id" in item:
        return {
            "tracker_id": item["tracker_id"],
        }

    raise RuntimeError(f"Unable to infer tracker key from item: {item}")


def _scan_simulatable_trackers() -> List[Dict[str, Any]]:
    table = _trackers_table()
    items: List[Dict[str, Any]] = []

    scan_kwargs = {
        "FilterExpression": Attr("simulation_enabled").eq(True) & Attr("tracker_id").exists()
    }

    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

    return items


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _next_position(latitude: float, longitude: float) -> Tuple[float, float]:
    lat_delta = random.uniform(-0.0007, 0.0007)
    lon_delta = random.uniform(-0.0007, 0.0007)

    next_lat = _clamp(latitude + lat_delta, -90.0, 90.0)
    next_lon = _clamp(longitude + lon_delta, -180.0, 180.0)

    return next_lat, next_lon


def _next_signal_quality(current_value: int) -> int:
    delta = random.randint(-2, 2)
    return int(_clamp(current_value + delta, 5, 31))


def _next_battery_voltage(current_value: float, external_power: bool) -> float:
    if external_power:
        delta = random.uniform(-0.01, 0.02)
        return round(_clamp(current_value + delta, 3.85, 4.20), 6)

    delta = random.uniform(-0.03, 0.005)
    return round(_clamp(current_value + delta, 3.40, 4.20), 6)


def _next_odometer(current_value: float, ignition: bool) -> float:
    if ignition:
        delta = random.uniform(0.05, 0.35)
    else:
        delta = random.uniform(0.0, 0.02)

    return round(max(0.0, current_value + delta), 3)


def _build_next_state(tracker: Dict[str, Any]) -> Dict[str, Any]:
    state_after = copy.deepcopy(tracker)

    latitude = _safe_float(tracker.get("latitude"), -25.515851)
    longitude = _safe_float(tracker.get("longitude"), -49.286927)
    signal_quality = _safe_int(tracker.get("signal_quality"), 20)
    battery_voltage = _safe_float(tracker.get("battery_voltage"), 3.98)
    odometer_km = _safe_float(tracker.get("odometer_km"), 0.0)

    ignition = bool(tracker.get("ignition", False))
    external_power = bool(tracker.get("external_power", True))

    next_latitude, next_longitude = _next_position(latitude, longitude)

    state_after["latitude"] = next_latitude
    state_after["longitude"] = next_longitude
    state_after["signal_quality"] = _next_signal_quality(signal_quality)
    state_after["battery_voltage"] = _next_battery_voltage(battery_voltage, external_power)
    state_after["odometer_km"] = _next_odometer(odometer_km, ignition)
    state_after["device_status"] = "ONLINE"
    state_after["gsm_registered"] = True

    return state_after


def _write_history(
    tracker_id: str,
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    timestamp: str
) -> None:
    item = {
        "pk": f"TRACKER#{tracker_id}",
        "sk": f"TS#{timestamp}",
        "tracker_id": tracker_id,
        "timestamp": timestamp,
        "event_type": SIMULATION_EVENT_TYPE,
        "command": SIMULATION_COMMAND_NAME,
        "response": SIMULATION_RESPONSE_TEXT,
        "result": SIMULATION_RESULT,
        "correlation_id": None,
        "model": state_after.get("model") or state_before.get("model"),
        "state_before": _to_decimal(state_before),
        "state_after": _to_decimal(state_after),
    }

    _history_table().put_item(Item=item)


def _apply_simulation_tick(tracker: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    tracker_id = tracker.get("tracker_id")
    if not tracker_id:
        logger.warning("simulation_skip_missing_tracker_id")
        return False, None

    tracker_key = _tracker_key(tracker)
    state_before = copy.deepcopy(tracker)
    state_after = _build_next_state(tracker)
    timestamp = _utc_now_iso()

    current_version = _safe_int(tracker.get("version"), 0)
    next_version = current_version + 1

    state_after["updated_at"] = timestamp
    state_after["version"] = next_version

    expression_attribute_names = {
        "#simulation_enabled": "simulation_enabled",
        "#version": "version",
        "#updated_at": "updated_at",
        "#latitude": "latitude",
        "#longitude": "longitude",
        "#signal_quality": "signal_quality",
        "#battery_voltage": "battery_voltage",
        "#odometer_km": "odometer_km",
        "#device_status": "device_status",
        "#gsm_registered": "gsm_registered",
    }

    expression_attribute_values = {
        ":expected_enabled": True,
        ":current_version": current_version,
        ":next_version": next_version,
        ":updated_at": _to_decimal(timestamp),
        ":latitude": _to_decimal(state_after["latitude"]),
        ":longitude": _to_decimal(state_after["longitude"]),
        ":signal_quality": _to_decimal(state_after["signal_quality"]),
        ":battery_voltage": _to_decimal(state_after["battery_voltage"]),
        ":odometer_km": _to_decimal(state_after["odometer_km"]),
        ":device_status": _to_decimal(state_after["device_status"]),
        ":gsm_registered": _to_decimal(state_after["gsm_registered"]),
    }

    update_expression = (
        "SET #updated_at = :updated_at, "
        "#version = :next_version, "
        "#latitude = :latitude, "
        "#longitude = :longitude, "
        "#signal_quality = :signal_quality, "
        "#battery_voltage = :battery_voltage, "
        "#odometer_km = :odometer_km, "
        "#device_status = :device_status, "
        "#gsm_registered = :gsm_registered"
    )

    condition_expression = (
        "#simulation_enabled = :expected_enabled AND "
        "(attribute_not_exists(#version) OR #version = :current_version)"
    )

    try:
        _trackers_table().update_item(
            Key=tracker_key,
            UpdateExpression=update_expression,
            ConditionExpression=condition_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )

        _write_history(
            tracker_id=tracker_id,
            state_before=state_before,
            state_after=state_after,
            timestamp=timestamp,
        )

        logger.info(
            "simulation_tick_success | tracker_id=%s | version=%s->%s",
            tracker_id,
            current_version,
            next_version,
        )

        return True, tracker_id

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            logger.info(
                "simulation_tick_skipped | tracker_id=%s | reason=disabled_or_version_conflict",
                tracker_id,
            )
            return False, tracker_id

        raise


def lambda_handler(event, context):
    try:
        trackers = _scan_simulatable_trackers()

        simulated_count = 0
        scanned_count = len(trackers)
        simulated_tracker_ids: List[str] = []
        skipped_tracker_ids: List[str] = []

        for tracker in trackers:
            simulated, tracker_id = _apply_simulation_tick(tracker)
            if simulated:
                simulated_count += 1
                if tracker_id:
                    simulated_tracker_ids.append(tracker_id)
            else:
                if tracker_id:
                    skipped_tracker_ids.append(tracker_id)

        logger.info(
            "simulation_run_finished | scanned=%s | simulated=%s | skipped=%s",
            scanned_count,
            simulated_count,
            len(skipped_tracker_ids),
        )

        return _response(
            200,
            {
                "message": f"Simulated {simulated_count} trackers",
                "scanned_count": scanned_count,
                "simulated_count": simulated_count,
                "skipped_count": len(skipped_tracker_ids),
                "simulated_tracker_ids": simulated_tracker_ids,
                "skipped_tracker_ids": skipped_tracker_ids,
            },
        )

    except Exception as exc:
        logger.exception("simulation_run_failed")
        return _response(
            500,
            {
                "message": "Simulation failed",
                "error": str(exc),
            },
        )
