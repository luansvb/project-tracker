import os


def _required_env(name: str) -> str:
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'Variável de ambiente {name} não configurada.')
    return value


def get_table_name() -> str:
    return _required_env('TRACKER_TABLE_NAME')


def get_history_table_name() -> str:
    return _required_env('HISTORY_TABLE_NAME')


def get_region() -> str:
    return os.environ.get('AWS_REGION', 'us-east-1').strip() or 'us-east-1'


def get_log_level() -> str:
    return os.environ.get('LOG_LEVEL', 'INFO').strip().upper() or 'INFO'
