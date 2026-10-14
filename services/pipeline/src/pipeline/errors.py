class APIError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status