import time

from f1ingest.http import RateLimiter


def test_stays_under_the_limit_within_the_window() -> None:
    limiter = RateLimiter(max_requests=2, period_s=0.2)
    start = time.monotonic()
    limiter.acquire()
    limiter.acquire()
    elapsed = time.monotonic() - start
    # Two calls within the allowance should not be throttled.
    assert elapsed < 0.1


def test_blocks_once_the_limit_is_exceeded() -> None:
    limiter = RateLimiter(max_requests=2, period_s=0.2)
    limiter.acquire()
    limiter.acquire()
    start = time.monotonic()
    limiter.acquire()  # third call within the window must wait
    elapsed = time.monotonic() - start
    assert elapsed >= 0.15  # allow a little scheduling slack under 0.2s
