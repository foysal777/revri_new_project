"""Reusable helpers for API operations."""

from .responses import success_response, error_response


def format_validation_errors(errors):
    if not errors:
        return []
    if isinstance(errors, dict):
        return [{"field": k, "errors": v} for k, v in errors.items()]
    return list(errors)


def bool_to_yes_no(value: bool) -> str:
    return "yes" if value else "no"


def use_success(data=None, message="Success"):
    return success_response(data=data, message=message)


def use_error(message="Error", errors=None):
    return error_response(message=message, errors=errors)
