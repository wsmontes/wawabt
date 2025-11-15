"""Lightweight retry helpers for pipelines and connectors."""
from __future__ import annotations

import random
import time
from typing import Callable, Tuple, TypeVar

T = TypeVar("T")


def _sleep(delay: float) -> None:  # pragma: no cover - simple shim
    time.sleep(delay)


def run_with_retry(
    func: Callable[..., T],
    *args,
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    jitter: float = 0.25,
    exceptions: Tuple[type[BaseException], ...] = (Exception,),
    logger=None,
    **kwargs,
) -> T:
    """Execute ``func`` with exponential backoff and jitter.

    Args:
        func: Callable to execute.
        attempts: Total attempts before re-raising.
        base_delay: Starting backoff in seconds.
        max_delay: Maximum sleep between retries.
        jitter: Random jitter factor (0-1) applied to delay.
        exceptions: Tuple of exception types that should trigger a retry.
        logger: Optional logger for warning messages.
    """

    delay = base_delay
    last_exc: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as exc:  # pragma: no cover - exercised via pipelines
            last_exc = exc
            if attempt == attempts:
                raise

            if logger:
                logger.warning(
                    "Retrying %s (%s/%s) after error: %s",
                    getattr(func, "__name__", func),
                    attempt,
                    attempts,
                    exc,
                )

            randomized = delay * (1 + random.uniform(-jitter, jitter))
            _sleep(max(0.0, min(randomized, max_delay)))
            delay = min(delay * 2, max_delay)

    # Should never reach here because loop either returns or raises
    raise RuntimeError(f"Retry loop for {func} exhausted without raising", last_exc)


def retry_decorator(**retry_kwargs):
    """Decorator form of :func:`run_with_retry`. Usage::

    @retry_decorator(attempts=5)
    def fetch():
        ...
    """

    def wrapper(func: Callable[..., T]) -> Callable[..., T]:
        def inner(*args, **kwargs):
            return run_with_retry(func, *args, **retry_kwargs, **kwargs)

        return inner

    return wrapper