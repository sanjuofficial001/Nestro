"""Base application exception structure.

The single exception all Nestro-specific errors derive from. Business exceptions
are added in future milestones; nothing exists yet beyond the base.
"""


class AppException(Exception):
    def __init__(self, *, status_code: int = 500, detail: str = "Internal server error") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)