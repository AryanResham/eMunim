class ServiceUnavailable(Exception):
    pass

class HostedError(Exception):
    def __init__(self, message, *, attempts=0, kind="provider_error"):
        super().__init__(message)
        self.attempts = attempts
        self.kind = kind
