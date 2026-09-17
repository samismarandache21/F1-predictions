"""Rate-limited, retrying, cached HTTP client for the OpenF1/Jolpica/Open-Meteo
adapters. CLAUDE.md rule 9: "Be polite to data sources. Rate-limit and use
exponential backoff."
"""

from __future__ import annotations

import time
from collections import deque
from types import TracebackType
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from f1ingest.cache import RawResponseCache


class RateLimiter:
    """Sliding-window limiter: at most `max_requests` calls per `period_s`.
    Blocking (`time.sleep`) rather than async — ingestion is a synchronous
    batch job in Phase 1, not part of the live request path.
    """

    def __init__(self, max_requests: int, period_s: float) -> None:
        self.max_requests = max_requests
        self.period_s = period_s
        self._timestamps: deque[float] = deque()

    def acquire(self) -> None:
        self._evict()
        if len(self._timestamps) >= self.max_requests:
            sleep_for = self.period_s - (time.monotonic() - self._timestamps[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._evict()
        self._timestamps.append(time.monotonic())

    def _evict(self) -> None:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > self.period_s:
            self._timestamps.popleft()


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class RateLimitedClient:
    """Wraps an httpx.Client with rate limiting, retries and a raw-response
    cache. One instance per source (OpenF1, Jolpica, ...): each has its own
    rate limit and its own cache subdirectory.
    """

    def __init__(
        self,
        source: str,
        base_url: str,
        *,
        cache: RawResponseCache,
        rate_limiters: list[RateLimiter] | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self.source = source
        self.cache = cache
        self.rate_limiters = rate_limiters or []
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RateLimitedClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def get_json(
        self, endpoint: str, params: dict[str, Any] | None = None, *, use_cache: bool = True
    ) -> Any:
        params = params or {}
        if use_cache:
            cached = self.cache.get(self.source, endpoint, params)
            if cached is not None:
                return cached

        payload = self._get_with_retry(endpoint, params)
        if use_cache:
            self.cache.put(self.source, endpoint, params, payload)
        return payload

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get_with_retry(self, endpoint: str, params: dict[str, Any]) -> Any:
        for limiter in self.rate_limiters:
            limiter.acquire()
        response = self._client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
