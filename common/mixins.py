from rest_framework import status
from rest_framework.response import Response


class JSONResponseMixin:
    """Mixin to standardize simple JSON response format."""

    def success(self, data=None, message="Success", status_code=status.HTTP_200_OK):
        payload = {"success": True, "message": message}
        if data is not None:
            payload["data"] = data
        return Response(payload, status=status_code)

    def error(self, message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        payload = {"success": False, "message": message}
        if errors is not None:
            payload["errors"] = errors
        return Response(payload, status=status_code)
