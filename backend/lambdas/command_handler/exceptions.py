class TrackerNotFoundError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


class UnsupportedCommandError(Exception):
    pass


class ConcurrencyConflictError(Exception):
    pass
