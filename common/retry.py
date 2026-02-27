"""Retry utility with exponential backoff for HTTP and API calls."""
from __future__ import annotations

import time
import functools
from typing import Any, Callable, Optional, Tuple, Type

# Default retryable exceptions
RETRYABLE = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import requests
    RETRYABLE = (*RETRYABLE, requests.exceptions.RequestException)
except ImportError:
    pass


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE,
    on_retry: Optional[Callable] = None,
):
    """Decorator: retry with exponential backoff.

    Args:
        max_attempts: Total attempts (1 = no retry).
        base_delay: Initial delay in seconds.
        max_delay: Cap on delay.
        backoff_factor: Multiplier per attempt.
        retryable_exceptions: Exception types that trigger retry.
        on_retry: Optional callback(attempt, exception) on each retry.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        raise
                    if on_retry:
                        on_retry(attempt, e)
                    time.sleep(min(delay, max_delay))
                    delay *= backoff_factor
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def retry_call(
    func: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE,
    default: Any = None,
) -> Any:
    """Functional retry: call func with retry, return default on exhaustion.

    Unlike the decorator, this swallows the final exception and returns default.
    """
    delay = base_delay
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **(kwargs or {}))
        except retryable_exceptions:
            if attempt == max_attempts:
                return default
            time.sleep(min(delay, max_delay))
            delay *= backoff_factor
    return default
