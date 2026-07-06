from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.response import Response


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = status.HTTP_200_OK,
) -> Response:
    payload: Dict[str, Any] = {
        "success": True,
        "message": message,
    }
    if data is not None:
        payload["data"] = data
    return Response(payload, status=status_code)


def created_response(data: Any = None, message: str = "Created") -> Response:
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def error_response(
    message: str = "Something went wrong",
    errors: Optional[Any] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    payload: Dict[str, Any] = {
        "success": False,
        "message": message,
    }
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=status_code)
