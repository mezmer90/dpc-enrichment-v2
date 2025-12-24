"""
Custom exceptions for API budget and rate limit errors

These exceptions signal that the enrichment should PAUSE (not fail)
and wait for the user to refresh API credits/limits.
"""


class APIBudgetError(Exception):
    """
    Raised when API budget/credits are exhausted.

    This is NOT a practice failure - it's a system-level issue
    that requires user intervention to refresh API credits.

    The enrichment should PAUSE and ask the user to:
    1. Add more credits to the API account
    2. Wait for rate limits to reset
    3. Resume the enrichment process

    Attributes:
        api_name: Name of the API (e.g., 'OpenRouter', 'ScraperAPI')
        message: Detailed error message
        original_error: Original exception from the API
    """

    def __init__(self, api_name: str, message: str, original_error: Exception = None):
        self.api_name = api_name
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{api_name}] {message}")


class APIRateLimitError(Exception):
    """
    Raised when API rate limit is hit.

    Similar to APIBudgetError, this is a system-level issue
    that requires pausing until rate limits reset.

    Attributes:
        api_name: Name of the API
        message: Detailed error message
        retry_after: Seconds to wait before retrying (if provided by API)
        original_error: Original exception from the API
    """

    def __init__(
        self,
        api_name: str,
        message: str,
        retry_after: int = None,
        original_error: Exception = None
    ):
        self.api_name = api_name
        self.message = message
        self.retry_after = retry_after
        self.original_error = original_error
        super().__init__(f"[{api_name}] {message}")


def detect_budget_error(error: Exception, api_name: str) -> bool:
    """
    Detect if an error is due to insufficient API budget/credits.

    Args:
        error: Exception from API call
        api_name: Name of the API ('OpenRouter', 'ScraperAPI', etc.)

    Returns:
        True if error is budget-related, False otherwise
    """
    error_str = str(error).lower()

    # Common budget/credits error patterns
    budget_keywords = [
        'insufficient funds',
        'insufficient credits',
        'out of credits',
        'balance',
        'quota exceeded',
        'payment required',
        'billing',
        'account suspended',
        'upgrade your plan',
        'credit limit',
        'no credits remaining',
    ]

    return any(keyword in error_str for keyword in budget_keywords)


def detect_rate_limit_error(error: Exception, api_name: str) -> bool:
    """
    Detect if an error is due to API rate limiting.

    Args:
        error: Exception from API call
        api_name: Name of the API

    Returns:
        True if error is rate limit-related, False otherwise
    """
    error_str = str(error).lower()

    # Common rate limit error patterns
    rate_limit_keywords = [
        'rate limit',
        'too many requests',
        'throttled',
        'slow down',
        'retry after',
        '429',  # HTTP 429 Too Many Requests
        'requests per',
        'rpm exceeded',
        'qpm exceeded',
    ]

    return any(keyword in error_str for keyword in rate_limit_keywords)


def detect_api_error_type(error: Exception, api_name: str) -> str:
    """
    Detect the type of API error.

    Args:
        error: Exception from API call
        api_name: Name of the API

    Returns:
        Error type: 'budget', 'rate_limit', or 'other'
    """
    if detect_budget_error(error, api_name):
        return 'budget'
    elif detect_rate_limit_error(error, api_name):
        return 'rate_limit'
    else:
        return 'other'
