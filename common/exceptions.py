from rest_framework.exceptions import APIException


class APIBusinessException(APIException):
    status_code = 400
    default_detail = "Business rule violation"
    default_code = "business_error"


class NotFoundException(APIBusinessException):
    status_code = 404
    default_detail = "Not found"
    default_code = "not_found"


class ConflictException(APIBusinessException):
    status_code = 409
    default_detail = "Conflict"
    default_code = "conflict"
