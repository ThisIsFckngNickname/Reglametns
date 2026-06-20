from typing import Any, Optional

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception with unified error format."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        field: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.code = code
        self.field = field
        self.message = message
        detail = {"code": code, "message": message, "field": field}
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=message,
            field=field,
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Resource already exists", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            message=message,
            field=field,
        )


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Invalid or expired token", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=message,
            field=field,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Insufficient permissions", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message,
            field=field,
        )


class CodeExpiredException(AppException):
    def __init__(self, message: str = "Verification code has expired. Request a new one."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CODE_EXPIRED",
            message=message,
            field="code",
        )


class BadRequestException(AppException):
    def __init__(self, code: str = "BAD_REQUEST", message: str = "Bad request", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=code,
            message=message,
            field=field,
        )


class RateLimitedException(AppException):
    def __init__(
        self,
        message: str = "Too many requests. Please try again in 15 minutes.",
        headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message=message,
            field=None,
            headers=headers,
        )


class FileTooLarge(AppException):
    def __init__(self, message: str = "File too large", field: Optional[str] = "file"):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="FILE_TOO_LARGE",
            message=message,
            field=field,
        )


class InvalidFileType(AppException):
    def __init__(self, message: str = "Invalid file type. Allowed: .docx, .pdf", field: Optional[str] = "file"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_FILE_TYPE",
            message=message,
            field=field,
        )


class ParseError(AppException):
    def __init__(self, message: str = "Failed to parse document", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="PARSE_ERROR",
            message=message,
            field=field,
        )


class NoActiveHolding(AppException):
    def __init__(self, message: str = "Выберите холдинг в профиле", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NO_ACTIVE_HOLDING",
            message=message,
            field=field,
        )
