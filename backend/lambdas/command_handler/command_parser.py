import re

from exceptions import UnsupportedCommandError

SUPPORTED_COMMANDS = {
    'STATUS#',
    'VERSION#',
    'PARAM#',
    'RELAY#',
    'RELAY,0#',
    'RELAY,1#',
}

COMMAND_PATTERNS = [
    re.compile(r'^STATUS#$', re.IGNORECASE),
    re.compile(r'^VERSION#$', re.IGNORECASE),
    re.compile(r'^PARAM#$', re.IGNORECASE),
    re.compile(r'^RELAY#$', re.IGNORECASE),
    re.compile(r'^RELAY,([01])#$', re.IGNORECASE),
]


def normalize_command(command: str) -> str:
    if not isinstance(command, str):
        raise UnsupportedCommandError('Comando deve ser uma string.')

    normalized = re.sub(r'\s+', '', command).upper()

    for pattern in COMMAND_PATTERNS:
        match = pattern.match(normalized)
        if match and normalized.startswith('RELAY,'):
            return f"RELAY,{match.group(1)}#"
        if match:
            return normalized

    raise UnsupportedCommandError(f'Comando não suportado nesta fase: {normalized}')
