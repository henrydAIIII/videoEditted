from typing import Any


def success_response(data: Any, message: str = "success") -> dict[str, Any]:
    return {
        "code": 0,
        "data": data,
        "message": message,
    }

