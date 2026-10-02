"""Minimal resilient HTTP GET for provider adapters: rate limiting, retries with exponential backoff and
secret-free error messages. The transport is injectable so adapters are testable offline."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

from packages.common.errors import DataError

log = logging.getLogger(__name__)

Transport = Callable[[str], bytes]
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class HttpStatusError(DataError):
    def __init__(self, status: int, safe_url: str) -> None:
        super().__init__(f"HTTP {status} from {safe_url}")
        self.status = status


def urllib_transport(timeout: float = 60.0, user_agent: str = "jev-sports-intelligence/0.1") -> Transport:
    def get(url: str) -> bytes:
        request = urllib.request.Request(
            url, headers={"User-Agent": user_agent, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as exc:
            # never echo the URL: it may carry the API key in the query string
            raise HttpStatusError(exc.code, "<redacted>") from None

    return get


@dataclass
class RateLimiter:
    """At most `max_per_window` calls per `window_seconds` (sliding window)."""

    max_per_window: int
    window_seconds: float
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _calls: list[float] = field(default_factory=list)

    def acquire(self) -> None:
        now = self.clock()
        self._calls = [t for t in self._calls if now - t < self.window_seconds]
        if len(self._calls) >= self.max_per_window:
            wait = self.window_seconds - (now - self._calls[0])
            if wait > 0:
                self.sleep(wait)
            now = self.clock()
            self._calls = [t for t in self._calls if now - t < self.window_seconds]
        self._calls.append(now)


@dataclass
class ResilientGetter:
    transport: Transport
    limiter: RateLimiter
    max_attempts: int = 4
    backoff_seconds: float = 2.0
    sleep: Callable[[float], None] = time.sleep
    stats: dict[str, int] = field(default_factory=lambda: {"requests": 0, "errors": 0, "retries": 0})

    def get(self, url: str, *, safe_url: str) -> bytes:
        """`safe_url` is the URL without secrets, the only form that may appear in logs and errors."""
        for attempt in range(1, self.max_attempts + 1):
            self.limiter.acquire()
            self.stats["requests"] += 1
            try:
                return self.transport(url)
            except HttpStatusError as exc:
                self.stats["errors"] += 1
                if exc.status not in RETRYABLE_STATUS or attempt == self.max_attempts:
                    raise HttpStatusError(exc.status, safe_url) from None
            except OSError as exc:  # network errors and timeouts
                self.stats["errors"] += 1
                if attempt == self.max_attempts:
                    raise DataError(f"network error from {safe_url}: {type(exc).__name__}") from None
            self.stats["retries"] += 1
            delay = self.backoff_seconds * 2 ** (attempt - 1)
            log.warning(
                "retrying provider request", extra={"url": safe_url, "attempt": attempt, "delay": delay}
            )
            self.sleep(delay)
        raise DataError(f"unreachable: {safe_url}")  # pragma: no cover
