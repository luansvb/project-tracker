import os
import random
from datetime import datetime, timezone
from decimal import Decimal

import boto3


TABLE_NAME = os.environ.get('TRACKER_TABLE_NAME')
HISTORY_TABLE_NAME = os.environ.get('HISTORY_TABLE_NAME')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
trackers_table = dynamodb.Table(TABLE_NAME)
history_table = dynamodb.Table(HISTORY_TABLE_NAME)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def to_decimal(value):
    return Decimal(str(value))


def simulate_tracker(tracker):
    # só simula se estiver habilitado
    if not tracker.get("simulation_enabled", False):
        return None

    updated = dict(tracker)

    # variação leve de posição
    lat = float(tracker.get("latitude", 0))
    lng = float(tracker.get("longitude", 0))

    lat += random.uniform(-0.0005, 0.0005)
    lng += random.uniform(-0.0005, 0.0005)

    # sinal
    signal = int(tracker.get("signal_quality", 0))
    signal = max(0, min(31, signal + random.randint(-2, 2)))

    # bateria
    battery = float(tracker.get("battery_voltage", 4.0))
    battery = max(3.5, min(4.2, battery + random.uniform(-0.01, 0.01)))

    updated["latitude"] = to_decimal(lat)
    updated["longitude"] = to_decimal(lng)
    updated["signal_quality"] = signal
    updated["battery_voltage"] = to_decimal(battery)
    updated["updated_at"] = now_iso()
    updated["version"] = int(tracker.get("version", 0)) + 1

    return updated


def save_history(before, after):
    history_table.put_item(
        Item={
            "pk": f"TRACKER#{after['tracker_id']}",
            "sk": f"TS#{now_iso()}",
            "tracker_id": after["tracker_id"],
            "timestamp": now_iso(),
            "event_type": "SIMULATION_TICK",
            "command": "SIMULATION",
            "response": "STATE_UPDATED",
            "result": "SUCCESS",
            "model": after.get("model"),
            "state_before": before,
            "state_after": after,
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

        processed += 1

    return {
        "statusCode": 200,
        "body": f"Simulated {processed} trackers"
    }
