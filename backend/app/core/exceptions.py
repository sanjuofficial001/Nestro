"""Base application exception structure.

The single exception all Nestro-specific errors derive from. Business exceptions
are added in future milestones; nothing exists yet beyond the base.
"""


class AppException(Exception):
    def __init__(self, *, status_code: int = 500, detail: str = "Internal server error") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AuthenticationError(AppException):
    """Failed identity verification — uniform 401 so clients cannot probe causes."""

    def __init__(self, *, status_code: int = 401, detail: str = "Authentication failed") -> None:
        super().__init__(status_code=status_code, detail=detail)


class AuthorizationError(AppException):
    """The authenticated user lacks the required role."""

    def __init__(self, *, status_code: int = 403, detail: str = "Forbidden") -> None:
        super().__init__(status_code=status_code, detail=detail)