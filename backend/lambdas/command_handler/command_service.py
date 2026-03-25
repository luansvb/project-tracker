from command_parser import normalize_command


def format_power_state(tracker: dict) -> str:
    return 'EXTERNAL' if tracker.get('external_power', True) else 'BATTERY'


def format_gsm_state(tracker: dict) -> str:
    return 'REGISTERED' if tracker.get('gsm_registered', True) else 'NO_SERVICE'


def format_relay_state(tracker: dict) -> str:
    return 'ON' if int(tracker.get('relay_state', 0)) == 1 else 'OFF'


def handle_status(tracker: dict) -> str:
    return (
        'STATUS;'
        f"POWER={format_power_state(tracker)};"
        f"IGN={'ON' if tracker.get('ignition', False) else 'OFF'};"
        f"GSM={format_gsm_state(tracker)};"
        f"SIGNAL={tracker.get('signal_quality', 0)};"
        f"BATTERY={tracker.get('battery_voltage', 0):.2f}V;"
        f"RELAY={format_relay_state(tracker)};"
        f"LAT={tracker.get('latitude', 0)};"
        f"LNG={tracker.get('longitude', 0)};"
        f"ODOMETER_KM={tracker.get('odometer_km', 0)}"
    )


def handle_version(tracker: dict) -> str:
    return (
        'VERSION;'
        f"MODEL={tracker.get('model', 'UNKNOWN')};"
        f"FW={tracker.get('firmware_version', 'UNKNOWN')};"
        f"HW={tracker.get('hardware_revision', 'UNKNOWN')}"
    )


def handle_param(tracker: dict) -> str:
    params = tracker.get('params', {})
    return (
        'PARAM;'
        f"APN={params.get('apn', 'internet')};"
        f"SERVER={params.get('server_host', 'simulator.local')}:{params.get('server_port', 0)};"
        f"HEARTBEAT_SEC={params.get('heartbeat_sec', 60)};"
        f"REPORT_SEC={params.get('report_interval_sec', 30)};"
        f"TIMEZONE={params.get('timezone', 'UTC-3')}"
    )


def handle_relay_get(tracker: dict) -> str:
    return f"RELAY;STATE={format_relay_state(tracker)}"


def process_read_command(tracker: dict, command: str) -> str:
    normalized = normalize_command(command)

    if normalized == 'STATUS#':
        return handle_status(tracker)
    if normalized == 'VERSION#':
        return handle_version(tracker)
    if normalized == 'PARAM#':
        return handle_param(tracker)
    if normalized == 'RELAY#':
        return handle_relay_get(tracker)

    return ''
