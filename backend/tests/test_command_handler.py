import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

COMMAND_HANDLER_DIR = Path(__file__).resolve().parents[1] / 'lambdas' / 'command_handler'
sys.path.insert(0, str(COMMAND_HANDLER_DIR))

os.environ.setdefault('TRACKER_TABLE_NAME', 'test-trackers')
os.environ.setdefault('HISTORY_TABLE_NAME', 'test-tracker-history')
os.environ.setdefault('AWS_REGION', 'us-east-1')

from command_parser import normalize_command  # noqa: E402
from command_service import process_read_command  # noqa: E402
from exceptions import InvalidRequestError, TrackerNotFoundError  # noqa: E402
import app  # noqa: E402


class DummyContext:
    aws_request_id = 'req-123'


@pytest.fixture
def base_tracker():
    return {
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
        'version': 0,
        'updated_at': '2026-03-23T00:00:00+00:00',
    }


def test_normalize_command_accepts_spacing_and_case():
    assert normalize_command(' relay, 1# ') == 'RELAY,1#'
    assert normalize_command('status#') == 'STATUS#'


def test_process_read_command_status(base_tracker):
    response = process_read_command(base_tracker, 'STATUS#')
    assert response.startswith('STATUS;')
    assert 'RELAY=OFF' in response


def test_parse_body_returns_normalized_command():
    payload = app.parse_body({'body': json.dumps({'tracker_id': ' tracker-1 ', 'command': ' relay, 0# '})})
    assert payload == {'tracker_id': 'tracker-1', 'command': 'RELAY,0#'}


def test_parse_history_limit_default_and_invalid():
    assert app.parse_history_limit({'queryStringParameters': None}) == 20

    with pytest.raises(InvalidRequestError):
        app.parse_history_limit({'queryStringParameters': {'limit': '0'}})

    with pytest.raises(InvalidRequestError):
        app.parse_history_limit({'queryStringParameters': {'limit': '101'}})

    with pytest.raises(InvalidRequestError):
        app.parse_history_limit({'queryStringParameters': {'limit': 'abc'}})


def test_lambda_handler_relay_on_updates_state_and_writes_history(monkeypatch, base_tracker):
    refreshed_tracker = {
        **base_tracker,
        'relay_state': 1,
        'version': 1,
        'updated_at': '2026-03-24T01:26:27.644778+00:00',
    }

    repository_mock = MagicMock()
    repository_mock.get_tracker.side_effect = [base_tracker, refreshed_tracker]
    repository_mock.update_relay_state.return_value = None

    history_repository_mock = MagicMock()
    history_repository_mock.put_command_event.return_value = {}

    monkeypatch.setattr(app, 'repository', repository_mock)
    monkeypatch.setattr(app, 'history_repository', history_repository_mock)

    event = {
        'rawPath': '/command',
        'body': json.dumps({'tracker_id': 'tracker-lt32-001', 'command': 'RELAY,1#'}),
        'requestContext': {
            'http': {'method': 'POST'},
            'requestId': 'corr-001',
            'routeKey': 'POST /command',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['success'] is True
    assert body['command'] == 'RELAY,1#'
    assert body['response'] == 'RELAY;STATE=ON;RESULT=OK'
    assert body['state_snapshot']['relay_state'] == 1
    assert body['state_snapshot']['version'] == 1

    repository_mock.update_relay_state.assert_called_once_with(base_tracker, 1, 'RELAY,1#')
    history_repository_mock.put_command_event.assert_called_once()

    history_call = history_repository_mock.put_command_event.call_args.kwargs
    assert history_call['tracker_id'] == 'tracker-lt32-001'
    assert history_call['command'] == 'RELAY,1#'
    assert history_call['response'] == 'RELAY;STATE=ON;RESULT=OK'
    assert history_call['result'] == 'SUCCESS'
    assert history_call['state_before']['relay_state'] == 0
    assert history_call['state_after']['relay_state'] == 1


def test_lambda_handler_relay_off_updates_state_and_writes_history(monkeypatch, base_tracker):
    tracker_on = {
        **base_tracker,
        'relay_state': 1,
        'version': 5,
        'updated_at': '2026-03-24T02:00:00+00:00',
    }
    refreshed_tracker = {
        **tracker_on,
        'relay_state': 0,
        'version': 6,
        'updated_at': '2026-03-24T02:01:00+00:00',
    }

    repository_mock = MagicMock()
    repository_mock.get_tracker.side_effect = [tracker_on, refreshed_tracker]
    repository_mock.update_relay_state.return_value = None

    history_repository_mock = MagicMock()
    history_repository_mock.put_command_event.return_value = {}

    monkeypatch.setattr(app, 'repository', repository_mock)
    monkeypatch.setattr(app, 'history_repository', history_repository_mock)

    event = {
        'rawPath': '/command',
        'body': json.dumps({'tracker_id': 'tracker-lt32-001', 'command': 'RELAY,0#'}),
        'requestContext': {
            'http': {'method': 'POST'},
            'requestId': 'corr-001b',
            'routeKey': 'POST /command',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['success'] is True
    assert body['command'] == 'RELAY,0#'
    assert body['response'] == 'RELAY;STATE=OFF;RESULT=OK'
    assert body['state_snapshot']['relay_state'] == 0
    assert body['state_snapshot']['version'] == 6

    repository_mock.update_relay_state.assert_called_once_with(tracker_on, 0, 'RELAY,0#')

    history_call = history_repository_mock.put_command_event.call_args.kwargs
    assert history_call['result'] == 'SUCCESS'
    assert history_call['state_before']['relay_state'] == 1
    assert history_call['state_after']['relay_state'] == 0


def test_lambda_handler_relay_off_noop_when_already_off(monkeypatch, base_tracker):
    repository_mock = MagicMock()
    repository_mock.get_tracker.return_value = base_tracker
    repository_mock.update_relay_state.return_value = None

    history_repository_mock = MagicMock()
    history_repository_mock.put_command_event.return_value = {}

    monkeypatch.setattr(app, 'repository', repository_mock)
    monkeypatch.setattr(app, 'history_repository', history_repository_mock)

    event = {
        'rawPath': '/command',
        'body': json.dumps({'tracker_id': 'tracker-lt32-001', 'command': 'RELAY,0#'}),
        'requestContext': {
            'http': {'method': 'POST'},
            'requestId': 'corr-002',
            'routeKey': 'POST /command',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['success'] is True
    assert body['command'] == 'RELAY,0#'
    assert body['response'] == 'RELAY;STATE=OFF;RESULT=NOOP'
    assert body['state_snapshot']['relay_state'] == 0
    assert body['state_snapshot']['version'] == 0

    repository_mock.update_relay_state.assert_not_called()

    history_call = history_repository_mock.put_command_event.call_args.kwargs
    assert history_call['result'] == 'NOOP'
    assert history_call['state_before'] == history_call['state_after']
    assert history_call['state_after']['relay_state'] == 0
    assert history_call['state_after']['version'] == 0


def test_lambda_handler_relay_on_noop_when_already_on(monkeypatch, base_tracker):
    tracker_on = {
        **base_tracker,
        'relay_state': 1,
        'version': 7,
        'updated_at': '2026-03-24T03:00:00+00:00',
    }

    repository_mock = MagicMock()
    repository_mock.get_tracker.return_value = tracker_on
    repository_mock.update_relay_state.return_value = None

    history_repository_mock = MagicMock()
    history_repository_mock.put_command_event.return_value = {}

    monkeypatch.setattr(app, 'repository', repository_mock)
    monkeypatch.setattr(app, 'history_repository', history_repository_mock)

    event = {
        'rawPath': '/command',
        'body': json.dumps({'tracker_id': 'tracker-lt32-001', 'command': 'RELAY,1#'}),
        'requestContext': {
            'http': {'method': 'POST'},
            'requestId': 'corr-003',
            'routeKey': 'POST /command',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['success'] is True
    assert body['command'] == 'RELAY,1#'
    assert body['response'] == 'RELAY;STATE=ON;RESULT=NOOP'
    assert body['state_snapshot']['relay_state'] == 1
    assert body['state_snapshot']['version'] == 7

    repository_mock.update_relay_state.assert_not_called()

    history_call = history_repository_mock.put_command_event.call_args.kwargs
    assert history_call['result'] == 'NOOP'
    assert history_call['state_before'] == history_call['state_after']
    assert history_call['state_after']['relay_state'] == 1
    assert history_call['state_after']['version'] == 7


def test_lambda_handler_get_tracker_returns_current_state(monkeypatch, base_tracker):
    repository_mock = MagicMock()
    repository_mock.get_tracker.return_value = base_tracker

    monkeypatch.setattr(app, 'repository', repository_mock)

    event = {
        'rawPath': '/trackers/tracker-lt32-001',
        'pathParameters': {'tracker_id': 'tracker-lt32-001'},
        'requestContext': {
            'http': {'method': 'GET'},
            'requestId': 'corr-004',
            'routeKey': 'GET /trackers/{tracker_id}',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['success'] is True
    assert body['tracker_id'] == 'tracker-lt32-001'
    assert body['model'] == 'LT32'
    assert body['state_snapshot']['relay_state'] == 0


def test_lambda_handler_get_tracker_history_returns_items(monkeypatch, base_tracker):
    repository_mock = MagicMock()
    repository_mock.get_tracker.return_value = base_tracker

    history_repository_mock = MagicMock()
    history_repository_mock.list_tracker_history.return_value = [
        {
            'timestamp': '2026-03-24T01:30:00+00:00',
            'event_type': 'COMMAND_EXECUTION',
            'command': 'RELAY,1#',
            'response': 'RELAY;STATE=ON;RESULT=OK',
            'result': 'SUCCESS',
            'correlation_id': 'corr-h1',
            'model': 'LT32',
            'state_before': {'relay_state': 0, 'version': 0},
            'state_after': {'relay_state': 1, 'version': 1},
        }
    ]

    monkeypatch.setattr(app, 'repository', repository_mock)
    monkeypatch.setattr(app, 'history_repository', history_repository_mock)

    event = {
        'rawPath': '/trackers/tracker-lt32-001/history',
        'pathParameters': {'tracker_id': 'tracker-lt32-001'},
        'queryStringParameters': {'limit': '10'},
        'requestContext': {
            'http': {'method': 'GET'},
            'requestId': 'corr-005',
            'routeKey': 'GET /trackers/{tracker_id}/history',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['success'] is True
    assert body['tracker_id'] == 'tracker-lt32-001'
    assert body['count'] == 1
    assert body['items'][0]['command'] == 'RELAY,1#'

    history_repository_mock.list_tracker_history.assert_called_once_with('tracker-lt32-001', 10)


def test_lambda_handler_tracker_not_found_returns_404(monkeypatch):
    repository_mock = MagicMock()
    repository_mock.get_tracker.side_effect = TrackerNotFoundError('Tracker não encontrado: tracker-x')

    monkeypatch.setattr(app, 'repository', repository_mock)

    event = {
        'rawPath': '/trackers/tracker-x',
        'pathParameters': {'tracker_id': 'tracker-x'},
        'requestContext': {
            'http': {'method': 'GET'},
            'requestId': 'corr-006',
            'routeKey': 'GET /trackers/{tracker_id}',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 404
    assert body['success'] is False
    assert 'Tracker não encontrado' in body['message']


def test_lambda_handler_unknown_route_returns_404():
    event = {
        'rawPath': '/unknown',
        'requestContext': {
            'http': {'method': 'GET'},
            'requestId': 'corr-007',
            'routeKey': 'GET /unknown',
        },
    }

    response = app.lambda_handler(event, DummyContext())
    body = json.loads(response['body'])

    assert response['statusCode'] == 404
    assert body['success'] is False
