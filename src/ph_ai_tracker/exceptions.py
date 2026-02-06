class PhAITrackerError(Exception):
    """Base exception for ph_ai_tracker."""


class APIError(PhAITrackerError):
    pass


class RateLimitError(APIError):
    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        rate_limit_limit: int | None = None,
        rate_limit_remaining: int | None = None,
        rate_limit_reset_seconds: int | None = None,
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.rate_limit_limit = rate_limit_limit
        self.rate_limit_remaining = rate_limit_remaining
        self.rate_limit_reset_seconds = rate_limit_reset_seconds


class ScraperError(PhAITrackerError):
    pass
