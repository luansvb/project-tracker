import os
import json
from decimal import Decimal
import boto3
from datetime import datetime, timezone

TABLE_NAME = os.environ.get('TRACKER_TABLE_NAME', 'tracker-simulator-dev-trackers')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def to_dynamodb(item: dict) -> dict:
    return json.loads(json.dumps(item), parse_float=Decimal)


TRACKERS = [
    {
        'tracker_id': 'tracker-lt32-001',
        'model': 'LT32',
        'device_status': 'ONLINE',
        'firmware_version': 'LT32_FW_1.4.2',
        'hardware_revision': 'LT32_REV_A',
        'external_power': True,
        'ignition': False,
        'gsm_registered': True,
        'signal_quality': 18,
        'battery_voltage': 4.08,
        'relay_state': 0,
        'latitude': -25.5043,
        'longitude': -49.2905,
        'odometer_km': 15432.6,
        'params': {
            'apn': 'iot.claro.com.br',
            'server_host': 'tracker-simulator.local',
            'server_port': 5001,
            'heartbeat_sec': 60,
            'report_interval_sec': 30,
            'timezone': 'UTC-3',
        },
        'simulation_enabled': True,
        'version': 0,
        'updated_at': now_iso(),
    },
    {
        'tracker_id': 'tracker-lt32pro-001',
        'model': 'LT32 PRO',
        'device_status': 'ONLINE',
        'firmware_version': 'LT32PRO_FW_2.1.0',
        'hardware_revision': 'LT32PRO_REV_B',
        'external_power': True,
        'ignition': True,
        'gsm_registered': True,
        'signal_quality': 22,
        'battery_voltage': 4.12,
        'relay_state': 1,
        'latitude': -25.5050,
        'longitude': -49.2910,
        'odometer_km': 9876.3,
        'params': {
            'apn': 'iot.vivo.com.br',
            'server_host': 'tracker-simulator.local',
            'server_port': 5001,
            'heartbeat_sec': 30,
            'report_interval_sec': 15,
            'timezone': 'UTC-3',
        },
        'simulation_enabled': True,
        'version': 0,
        'updated_at': now_iso(),
    },
    {
        'tracker_id': 'tracker-lt32-002',
        'model': 'LT32',
        'device_status': 'OFFLINE',
        'firmware_version': 'LT32_FW_1.3.9',
        'hardware_revision': 'LT32_REV_A',
        'external_power': False,
        'ignition': False,
        'gsm_registered': False,
        'signal_quality': 0,
        'battery_voltage': 3.65,
        'relay_state': 0,
        'latitude': -25.6000,
        'longitude': -49.3500,
        'odometer_km': 20000.0,
        'params': {
            'apn': 'iot.tim.com.br',
            'server_host': 'tracker-simulator.local',
            'server_port': 5001,
            'heartbeat_sec': 120,
            'report_interval_sec': 60,
            'timezone': 'UTC-3',
        },
        'simulation_enabled': False,
        'version': 0,
        'updated_at': now_iso(),
    },
]


def seed():
    for tracker in TRACKERS:
        table.put_item(Item=to_dynamodb(tracker))
        print(f"Seedado: {tracker['tracker_id']} ({tracker['model']})")

    print(f"\nConcluído. {len(TRACKERS)} trackers gravados em {TABLE_NAME} na região {REGION}.")


if __name__ == '__main__':
    seed()
