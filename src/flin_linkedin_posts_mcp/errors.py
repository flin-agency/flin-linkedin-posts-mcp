from __future__ import annotations


class LinkedInPostsError(Exception):
    error_code = "linkedin_api_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.details = details or {}


class LinkedInAuthError(LinkedInPostsError):
    error_code = "auth_error"


class LinkedInPermissionError(LinkedInPostsError):
    error_code = "permission_error"


class LinkedInRateLimitError(LinkedInPostsError):
    error_code = "rate_limit_error"


class LinkedInValidationError(LinkedInPostsError):
    error_code = "validation_error"


class LinkedInAPIError(LinkedInPostsError):
    error_code = "linkedin_api_error"
