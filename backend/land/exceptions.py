"""
Custom exceptions for the land app.

Existing code keeps the {success: False} dict pattern for backward compat.
These exceptions are for new code and cleaner error handling.
"""


class LandError(Exception):
    """Base exception for land app errors."""


class VworldAPIError(LandError):
    """Vworld API call failed."""

    def __init__(self, message: str, api_name: str = "", status_code: int | None = None):
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(message)


class PnuValidationError(LandError):
    """Invalid PNU code."""

    def __init__(self, pnu: str):
        self.pnu = pnu
        super().__init__(f"Invalid PNU format (expected 19 digits): {pnu}")


class LawSearchError(LandError):
    """Law article search failed."""

    def __init__(self, message: str, query: str = ""):
        self.query = query
        super().__init__(message)
