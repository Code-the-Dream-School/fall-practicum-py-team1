class APIError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status

class MalformedPayloadError(Exception):
    def __init__(self, message):
        super().__init__(message)

ERROR_MESSAGES = {
    400: "Bad request: check your parameters.",
    401: "Invalid or missing API key.",
    403: "Key is valid but not allowed to access this resource.",
    404: "Not found: bad URL or unknown city.",
}

RETRY_STATUSES = {429, 500, 502, 503, 504}