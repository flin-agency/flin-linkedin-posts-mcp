from __future__ import annotations


class LinkedInAdsError(Exception):
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


class LinkedInAuthError(LinkedInAdsError):
    error_code = "auth_error"


class LinkedInPermissionError(LinkedInAdsError):
    error_code = "permission_error"


class LinkedInRateLimitError(LinkedInAdsError):
    error_code = "rate_limit_error"


class LinkedInValidationError(LinkedInAdsError):
    error_code = "validation_error"


class LinkedInAPIError(LinkedInAdsError):
    error_code = "linkedin_api_error"


class AccountSelectionRequired(Exception):
    def __init__(self, *, choices: list[dict[str, str]], message: str | None = None) -> None:
        self.choices = choices
        super().__init__(message or "Multiple ad accounts found. Please choose ad_account_id.")
