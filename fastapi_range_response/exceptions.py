import json

from starlette import status as http_status

from starlette.exceptions import HTTPException

__all__ = [
    'RangeNotSatisfiableError',
    'MalformedRangeHeaderError'
]


class RangeNotSatisfiableError(HTTPException):
    def __init__(self, max_size: int) -> None:
        super().__init__(http_status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, json.dumps({"Content-Range": f"*/{max_size}"}))


class MalformedRangeHeaderError(HTTPException):
    def __init__(self, message: str = "Malformed Range header") -> None:
        super().__init__(http_status.HTTP_400_BAD_REQUEST, message)

