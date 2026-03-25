import json

from botocore.exceptions import ClientError

from command_parser import normalize_command
from command_service import process_read_command
from exceptions import (
    ConcurrencyConflictError,
    InvalidRequestError,
    TrackerNotFoundError,
    UnsupportedCommandError,
)
from history_repository import HistoryRepository
from logging_utils import log_json
from repository import TrackerRepository
from responses import json_response
from utils import now_iso

repository = TrackerRepository()
history_repository = HistoryRepository()


def parse_body(event: dict) -> dict:
    body = event.get('body')
    if not body:
        raise InvalidRequestError('Body ausente.')

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvalidRequestError('Body precisa estar em JSON válido.') from exc

    tracker_id = payload.get('tracker_id')
    command = payload.get('command')

    if not tracker_id or not isinstance(tracker_id, str):
        raise InvalidRequestError("Campo 'tracker_id' é obrigatório e deve ser string.")
    if not command or not isinstance(command, str):
        raise InvalidRequestError("Campo 'command' é obrigatório e deve ser string.")

    normalized_command = normalize_command(command)

    return {
        'tracker_id': tracker_id.strip(),
        'command': normalized_command,
    }


def build_state_snapshot(tracker: dict) -> dict:
    return {
        'relay_state': tracker.get('relay_state'),
        'ignition': tracker.get('ignition'),
        'external_power': tracker.get('external_power'),
        'gsm_registered': tracker.get('gsm_registered'),
        'signal_quality': tracker.get('signal_quality'),
        'battery_voltage': tracker.get('battery_voltage'),
        'simulation_enabled': tracker.get('simulation_enabled', False),
        'updated_at': tracker.get('updated_at'),
        'version': tracker.get('version', 0),
    }


def extract_tracker_id_from_path(event: dict) -> str:
    path_parameters = event.get('pathParameters') or {}
    tracker_id = path_parameters.get('tracker_id')

    if not tracker_id or not isinstance(tracker_id, str):
        raise InvalidRequestError('tracker_id ausente na rota.')

    return tracker_id.strip()


def parse_history_limit(event: dict) -> int:
    query_params = event.get('queryStringParameters') or {}
    raw_limit = query_params.get('limit')

    if raw_limit in (None, ''):
        return 20

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise InvalidRequestError("Query string 'limit' deve ser um inteiro entre 1 e 100.") from exc

    if limit < 1 or limit > 100:
        raise InvalidRequestError("Query string 'limit' deve ser um inteiro entre 1 e 100.")

    return limit


def format_history_item(item: dict) -> dict:
    return {
        'timestamp': item.get('timestamp'),
        'event_type': item.get('event_type'),
        'command': item.get('command'),
        'response': item.get('response'),
        'result': item.get('result'),
        'correlation_id': item.get('correlation_id'),
        'model': item.get('model'),
        'state_before': item.get('state_before'),
        'state_after': item.get('state_after'),
    }


def handle_health(correlation_id: str) -> dict:
    log_json('info', 'Health check processado', correlation_id=correlation_id, route='GET /health')
    return json_response(
        200,
        {
            'ok': True,
            'service': 'tracker-command-handler',
            'timestamp': now_iso(),
            'correlation_id': correlation_id,
        },
    )


def handle_get_tracker(event: dict, correlation_id: str) -> dict:
    tracker_id = extract_tracker_id_from_path(event)
    tracker = repository.get_tracker(tracker_id)

    log_json(
        'info',
        'Consulta de tracker processada',
        correlation_id=correlation_id,
        route='GET /trackers/{tracker_id}',
        tracker_id=tracker_id,
    )

    return json_response(
        200,
        {
            'success': True,
            'tracker_id': tracker['tracker_id'],
            'model': tracker.get('model'),
            'device_status': tracker.get('device_status'),
            'simulation_enabled': tracker.get('simulation_enabled', False),
            'updated_at': tracker.get('updated_at'),
            'state_snapshot': build_state_snapshot(tracker),
            'correlation_id': correlation_id,
        },
    )


def handle_get_tracker_history(event: dict, correlation_id: str) -> dict:
    tracker_id = extract_tracker_id_from_path(event)
    limit = parse_history_limit(event)

    repository.get_tracker(tracker_id)
    items = history_repository.list_tracker_history(tracker_id, limit)

    log_json(
        'info',
        'Consulta de histórico processada',
        correlation_id=correlation_id,
        route='GET /trackers/{tracker_id}/history',
        tracker_id=tracker_id,
        limit=limit,
        count=len(items),
    )

    return json_response(
        200,
        {
            'success': True,
            'tracker_id': tracker_id,
            'count': len(items),
            'items': [format_history_item(item) for item in items],
            'correlation_id': correlation_id,
        },
    )


def handle_command(event: dict, correlation_id: str) -> dict:
    payload = parse_body(event)
    tracker_id = payload['tracker_id']
    normalized_command = payload['command']

    log_json(
        'info',
        'Comando recebido',
        correlation_id=correlation_id,
        route='POST /command',
        tracker_id=tracker_id,
        command=normalized_command,
    )

    tracker = repository.get_tracker(tracker_id)
    state_before = build_state_snapshot(tracker)

    if normalized_command in {'RELAY,0#', 'RELAY,1#'}:
        desired_state = 0 if normalized_command == 'RELAY,0#' else 1

        if tracker.get('relay_state') == desired_state:
            refreshed_tracker = tracker
            state_after = state_before
            response_text = f"RELAY;STATE={'OFF' if desired_state == 0 else 'ON'};RESULT=NOOP"
            command_result = 'NOOP'
        else:
            repository.update_relay_state(tracker, desired_state, normalized_command)
            refreshed_tracker = repository.get_tracker(tracker_id)
            state_after = build_state_snapshot(refreshed_tracker)
            response_text = f"RELAY;STATE={'OFF' if desired_state == 0 else 'ON'};RESULT=OK"
            command_result = 'SUCCESS'
    else:
        response_text = process_read_command(tracker, normalized_command)
        refreshed_tracker = repository.get_tracker(tracker_id)
        state_after = build_state_snapshot(refreshed_tracker)
        command_result = 'SUCCESS'

    history_repository.put_command_event(
        tracker_id=refreshed_tracker['tracker_id'],
        model=refreshed_tracker.get('model', 'UNKNOWN'),
        command=normalized_command,
        response=response_text,
        correlation_id=correlation_id,
        result=command_result,
        state_before=state_before,
        state_after=state_after,
    )

    log_json(
        'info',
        'Comando processado com sucesso',
        correlation_id=correlation_id,
        tracker_id=tracker_id,
        command=normalized_command,
        result=command_result.lower(),
        version=refreshed_tracker.get('version', 0),
    )

    return json_response(
        200,
        {
            'success': True,
            'tracker_id': refreshed_tracker['tracker_id'],
            'model': refreshed_tracker.get('model'),
            'command': normalized_command,
            'response': response_text,
            'state_snapshot': state_after,
            'correlation_id': correlation_id,
        },
    )


def route_request(event: dict, aws_request_id: str) -> dict:
    request_context = event.get('requestContext', {})
    http = request_context.get('http', {})
    method = http.get('method', '')
    path = event.get('rawPath', '')
    route_key = request_context.get('routeKey', f'{method} {path}')
    correlation_id = request_context.get('requestId', aws_request_id)

    if route_key == 'GET /health' or (method == 'GET' and path == '/health'):
        return handle_health(correlation_id)

    if route_key == 'POST /command' or (method == 'POST' and path == '/command'):
        return handle_command(event, correlation_id)

    if route_key == 'GET /trackers/{tracker_id}/history':
        return handle_get_tracker_history(event, correlation_id)

    if route_key == 'GET /trackers/{tracker_id}':
        return handle_get_tracker(event, correlation_id)

    log_json('warning', 'Rota não encontrada', correlation_id=correlation_id, route=f'{method} {path}')
    return json_response(
        404,
        {
            'success': False,
            'message': f'Rota não encontrada: {method} {path}',
            'correlation_id': correlation_id,
        },
    )


def lambda_handler(event, context):
    aws_request_id = getattr(context, 'aws_request_id', 'unknown')

    try:
        log_json('info', 'Invocação iniciada', aws_request_id=aws_request_id)
        return route_request(event, aws_request_id)
    except InvalidRequestError as exc:
        log_json('warning', 'Requisição inválida', aws_request_id=aws_request_id, error=str(exc))
        return json_response(400, {'success': False, 'message': str(exc), 'correlation_id': aws_request_id})
    except TrackerNotFoundError as exc:
        log_json('warning', 'Tracker não encontrado', aws_request_id=aws_request_id, error=str(exc))
        return json_response(404, {'success': False, 'message': str(exc), 'correlation_id': aws_request_id})
    except UnsupportedCommandError as exc:
        log_json('warning', 'Comando não suportado', aws_request_id=aws_request_id, error=str(exc))
        return json_response(422, {'success': False, 'message': str(exc), 'correlation_id': aws_request_id})
    except ConcurrencyConflictError as exc:
        log_json('warning', 'Conflito de concorrência', aws_request_id=aws_request_id, error=str(exc))
        return json_response(409, {'success': False, 'message': str(exc), 'correlation_id': aws_request_id})
    except ClientError as exc:
        log_json('error', 'Erro AWS', aws_request_id=aws_request_id, error=str(exc))
        return json_response(
            500,
            {'success': False, 'message': 'Erro AWS ao processar a requisição.', 'correlation_id': aws_request_id},
        )
    except Exception as exc:
        log_json('error', 'Erro interno inesperado', aws_request_id=aws_request_id, error=str(exc))
        return json_response(
            500,
            {'success': False, 'message': 'Erro interno inesperado.', 'correlation_id': aws_request_id},
        )

