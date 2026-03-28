import os
import random
from datetime import datetime, timezone
from decimal import Decimal

import boto3


TABLE_NAME = os.environ.get("TRACKER_TABLE_NAME")
HISTORY_TABLE_NAME = os.environ.get("HISTORY_TABLE_NAME")
TELEMETRY_TABLE_NAME = os.environ.get("TELEMETRY_TABLE_NAME")
REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
trackers_table = dynamodb.Table(TABLE_NAME)
history_table = dynamodb.Table(HISTORY_TABLE_NAME)
telemetry_table = dynamodb.Table(TELEMETRY_TABLE_NAME)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_decimal(value) -> Decimal:
    return Decimal(str(value))


def to_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def simulate_tracker(tracker: dict) -> dict | None:
    if not tracker.get("simulation_enabled", False):
        return None

    updated = dict(tracker)

    lat = to_float(tracker.get("latitude"), 0.0)
    lng = to_float(tracker.get("longitude"), 0.0)
    signal = to_int(tracker.get("signal_quality"), 0)
    battery = to_float(tracker.get("battery_voltage"), 4.0)
    odometer = to_float(tracker.get("odometer_km"), 0.0)
    ignition = bool(tracker.get("ignition", False))

    signal = max(0, min(31, signal + random.randint(-2, 2)))
    battery = max(3.5, min(4.2, battery + random.uniform(-0.01, 0.01)))

    if ignition:
        speed = random.randint(18, 62)
        lat += random.uniform(-0.0005, 0.0005)
        lng += random.uniform(-0.0005, 0.0005)
        odometer += (speed / 3600.0) * 30.0
    else:
        speed = 0

    updated["latitude"] = to_decimal(round(lat, 6))
    updated["longitude"] = to_decimal(round(lng, 6))
    updated["signal_quality"] = signal
    updated["battery_voltage"] = to_decimal(round(battery, 3))
    updated["odometer_km"] = to_decimal(round(odometer, 3))
    updated["speed_kmh"] = speed
    updated["updated_at"] = now_iso()
    updated["version"] = to_int(tracker.get("version"), 0) + 1

    return updated


def save_history(before: dict, after: dict) -> None:
    timestamp = now_iso()

    history_table.put_item(
        Item={
            "pk": f"TRACKER#{after['tracker_id']}",
            "sk": f"TS#{timestamp}",
            "tracker_id": after["tracker_id"],
            "timestamp": timestamp,
            "event_type": "SIMULATION_TICK",
            "command": "SIMULATION",
            "response": "STATE_UPDATED",
            "result": "SUCCESS",
            "model": after.get("model"),
            "state_before": before,
            "state_after": after,
        }
    )


def save_telemetry(tracker: dict) -> None:
    recorded_at = now_iso()

    telemetry_table.put_item(
        Item={
            "tracker_id": tracker["tracker_id"],
            "recorded_at": recorded_at,
            "device_status": tracker.get("device_status", "UNKNOWN"),
            "model": tracker.get("model", "UNKNOWN"),
            "simulation_enabled": bool(tracker.get("simulation_enabled", False)),
            "ignition": bool(tracker.get("ignition", False)),
            "external_power": bool(tracker.get("external_power", True)),
            "gsm_registered": bool(tracker.get("gsm_registered", True)),
            "relay_state": to_int(tracker.get("relay_state"), 0),
            "signal_quality": to_int(tracker.get("signal_quality"), 0),
            "battery_voltage": to_decimal(round(to_float(tracker.get("battery_voltage"), 0.0), 3)),
            "speed_kmh": to_int(tracker.get("speed_kmh"), 0),
            "odometer_km": to_decimal(round(to_float(tracker.get("odometer_km"), 0.0), 3)),
            "latitude": to_decimal(round(to_float(tracker.get("latitude"), 0.0), 6)),
            "longitude": to_decimal(round(to_float(tracker.get("longitude"), 0.0), 6)),
            "updated_at": tracker.get("updated_at", recorded_at),
        }
    )


def lambda_handler(event, context):
    response = trackers_table.scan()
    items = response.get("Items", [])

    processed = 0

    for tracker in items:
        updated = simulate_tracker(tracker)

        if not updated:
            continue

        trackers_table.put_item(Item=updated)
        save_history(tracker, updated)
        save_telemetry(updated)

        processed += 1

    return {
        "statusCode": 200,
        "body": f"Simulated {processed} trackers and stored telemetry"
    }
