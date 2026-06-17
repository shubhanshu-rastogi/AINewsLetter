"""Application-level exception hierarchy.

These exceptions carry an HTTP status code and a stable machine-readable
``code`` so the error-handling middleware can translate them into consistent
API error responses.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppException):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppException):
    status_code = 409
    code = "conflict"
    message = "Resource conflict."


class ValidationAppError(AppException):
    status_code = 422
    code = "validation_error"
    message = "Request validation failed."


class UnauthorizedError(AppException):
    status_code = 401
    code = "unauthorized"
    message = "Authentication required."


class ForbiddenError(AppException):
    status_code = 403
    code = "forbidden"
    message = "Operation not permitted."


class ServiceUnavailableError(AppException):
    status_code = 503
    code = "service_unavailable"
    message = "A dependency is unavailable."
