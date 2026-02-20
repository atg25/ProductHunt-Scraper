"""Exception hierarchy for ph_ai_tracker.

All exceptions raised by this library are subclasses of ``PhAITrackerError``
so callers can catch the entire family with a single ``except`` clause when
need be.

Hierarchy::

    PhAITrackerError
    ├── APIError            – any Product Hunt API failure
    │   └── RateLimitError  – HTTP 429; carries retry/reset metadata
    ├── ScraperError        – network-layer scraping failure (not a parse error)
    └── StorageError        – SQLite write/read failure
"""


class PhAITrackerError(Exception):
    """Base exception for all ph_ai_tracker errors."""


class APIError(PhAITrackerError):
    """Raised when the Product Hunt GraphQL API returns an unexpected response."""


class RateLimitError(APIError):
    """Raised when the API responds with HTTP 429 (Too Many Requests).

    Attributes:
        retry_after_seconds: Seconds to wait before retrying (from
            ``Retry-After`` or ``X-Rate-Limit-Reset`` headers), or ``None``.
        rate_limit_limit: Total request quota for the period.
        rate_limit_remaining: Remaining quota (typically 0 on a 429).
        rate_limit_reset_seconds: Epoch seconds when the quota resets.
    """

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
    """Raised on a network-layer scraping failure (timeout, HTTP 4xx/5xx).

    Parse errors and empty pages are *not* raised as ``ScraperError``; they
    degrade gracefully and are logged at WARNING level instead.
    """


class StorageError(PhAITrackerError):
    """Raised when a SQLite read or write operation fails.

    Wraps both ``sqlite3.Error`` and ``sqlite3.IntegrityError`` so callers
    receive a single typed exception regardless of the SQLite failure mode.
    """
