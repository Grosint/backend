from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import sanitize_log_data

logger = logging.getLogger(__name__)


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitConfig:
    failure_threshold: int = 3
    recovery_timeout_seconds: int = 60
    half_open_probe_attempts: int = 1


class CircuitBreaker:
    """Simple circuit breaker per key (e.g., host or adapter name)."""

    def __init__(self, config: CircuitConfig | None = None):
        self._config = config or CircuitConfig(
            failure_threshold=settings.CB_FAILURE_THRESHOLD,
            recovery_timeout_seconds=settings.CB_RECOVERY_TIMEOUT_SECONDS,
            half_open_probe_attempts=settings.CB_HALF_OPEN_PROBE_ATTEMPTS,
        )
        # key -> state
        self._state: dict[str, str] = {}
        self._failure_count: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}
        self._half_open_inflight: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def allow_request(self, key: str) -> bool:
        async with self._lock:
            state = self._state.get(key, CircuitState.CLOSED)

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                opened_at = self._opened_at.get(key, 0)
                if time.time() - opened_at >= self._config.recovery_timeout_seconds:
                    # Move to half-open
                    self._state[key] = CircuitState.HALF_OPEN
                    self._half_open_inflight[key] = 0
                else:
                    return False

            if self._state.get(key) == CircuitState.HALF_OPEN:
                # Allow only limited probe attempts concurrently
                inflight = self._half_open_inflight.get(key, 0)
                if inflight < self._config.half_open_probe_attempts:
                    self._half_open_inflight[key] = inflight + 1
                    return True
                return False

            return True

    async def on_success(self, key: str) -> None:
        async with self._lock:
            self._failure_count[key] = 0
            prev_state = self._state.get(key, CircuitState.CLOSED)
            self._state[key] = CircuitState.CLOSED
            self._opened_at.pop(key, None)
            if prev_state != CircuitState.CLOSED:
                logger.info(
                    "Circuit closed",
                    extra={"cb_key": key, "prev_state": prev_state},
                )
            # Reset half-open inflight counter if present
            if key in self._half_open_inflight:
                self._half_open_inflight[key] = 0

    async def on_failure(self, key: str) -> None:
        async with self._lock:
            count = self._failure_count.get(key, 0) + 1
            self._failure_count[key] = count

            state = self._state.get(key, CircuitState.CLOSED)
            if state == CircuitState.HALF_OPEN:
                # Trip back to open on any failure in half-open
                self._trip_open(key)
                return

            if count >= self._config.failure_threshold and state != CircuitState.OPEN:
                self._trip_open(key)

    def _trip_open(self, key: str) -> None:
        self._state[key] = CircuitState.OPEN
        self._opened_at[key] = time.time()
        logger.warning(
            "Circuit opened",
            extra={
                "cb_key": key,
                "failure_threshold": self._config.failure_threshold,
                "recovery_timeout_seconds": self._config.recovery_timeout_seconds,
            },
        )


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.2
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.2
    retry_on_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    retry_on_exceptions: tuple[type[BaseException], ...] = (
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.RemoteProtocolError,
        httpx.NetworkError,
    )

    def compute_backoff(self, attempt: int) -> float:
        base = self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt - 1))
        # Using random.random() for jitter is acceptable here (not cryptographic use)
        jitter = base * self.jitter_ratio * (2 * random.random() - 1)  # nosec B311
        return max(0.0, base + jitter)


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int | None = None):
        self._semaphore = asyncio.Semaphore(
            max_concurrent or settings.MAX_CONCURRENT_REQUESTS
        )

    @asynccontextmanager
    async def slot(self):
        await self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()


class ResilientHttpClient:
    """
    httpx.AsyncClient wrapper with timeout, retry, circuit breaker, and concurrency limiting.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        concurrency_limiter: ConcurrencyLimiter | None = None,
        proxies: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._timeout = timeout_seconds or float(settings.EXTERNAL_API_TIMEOUT)
        self._retry = retry_policy or RetryPolicy(
            max_attempts=settings.RETRY_MAX_ATTEMPTS,
            initial_backoff_seconds=settings.RETRY_INITIAL_BACKOFF_SECONDS,
            backoff_multiplier=settings.RETRY_BACKOFF_MULTIPLIER,
            jitter_ratio=settings.RETRY_JITTER_RATIO,
        )
        self._circuit = circuit_breaker or CircuitBreaker()
        self._limit = concurrency_limiter or ConcurrencyLimiter()

        # Build client kwargs conditionally
        client_kwargs = {"timeout": self._timeout}
        if proxies is not None:
            client_kwargs["proxies"] = proxies
        if headers is not None:
            client_kwargs["headers"] = headers

        self._client = httpx.AsyncClient(**client_kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        allowed_statuses: Iterable[int] | None = None,
        circuit_key: str | None = None,
    ) -> httpx.Response:
        key = circuit_key or self._extract_host(url)

        # Sanitize URL for logging to prevent PII leakage
        sanitized_url = sanitize_log_data({"url": url}).get("url", url)

        if not await self._circuit.allow_request(key):
            logger.warning(
                "Circuit open - short-circuiting request",
                extra={"cb_key": key, "url": sanitized_url},
            )
            raise httpx.RequestError(f"Circuit open for {key}")

        attempt = 0
        last_exc: BaseException | None = None
        allowed = set(allowed_statuses or [])

        async with self._limit.slot():
            while attempt < self._retry.max_attempts:
                attempt += 1
                try:
                    start = time.perf_counter()
                    response = await self._client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        json=json,
                        data=data,
                    )
                    latency_ms = int((time.perf_counter() - start) * 1000)

                    if response.status_code in allowed or (response.status_code < 400):
                        await self._circuit.on_success(key)
                        logger.info(
                            "HTTP request success",
                            extra={
                                "url": sanitized_url,
                                "method": method,
                                "status": response.status_code,
                                "latency_ms": latency_ms,
                            },
                        )
                        return response

                    # Retryable status?
                    if (
                        response.status_code in self._retry.retry_on_statuses
                        and attempt < self._retry.max_attempts
                    ):
                        backoff = self._retry.compute_backoff(attempt)
                        logger.warning(
                            "HTTP retry on status",
                            extra={
                                "url": sanitized_url,
                                "method": method,
                                "status": response.status_code,
                                "attempt": attempt,
                                "backoff_seconds": round(backoff, 3),
                            },
                        )
                        await asyncio.sleep(backoff)
                        continue

                    # Non-retryable status -> failure
                    await self._circuit.on_failure(key)
                    logger.error(
                        "HTTP request failed",
                        extra={
                            "url": sanitized_url,
                            "method": method,
                            "status": response.status_code,
                            "response": sanitize_log_data(
                                {"text": response.text[:512]}
                            ),
                        },
                    )
                    response.raise_for_status()
                    return response

                except self._retry.retry_on_exceptions as exc:  # type: ignore[misc]
                    last_exc = exc
                    await self._circuit.on_failure(key)
                    if attempt < self._retry.max_attempts:
                        backoff = self._retry.compute_backoff(attempt)
                        logger.warning(
                            "HTTP retry on exception",
                            extra={
                                "url": sanitized_url,
                                "method": method,
                                "attempt": attempt,
                                "exception": type(exc).__name__,
                                "backoff_seconds": round(backoff, 3),
                            },
                        )
                        await asyncio.sleep(backoff)
                        continue
                    logger.error(
                        "HTTP request error - giving up",
                        extra={
                            "url": sanitized_url,
                            "method": method,
                            "exception": type(exc).__name__,
                        },
                    )
                    raise
                except httpx.HTTPError as exc:
                    # Catch-all for any httpx errors not in retry_on_exceptions
                    # This ensures circuit breaker records failures for all HTTP errors
                    last_exc = exc
                    await self._circuit.on_failure(key)
                    logger.error(
                        "HTTP request error - non-retryable exception",
                        extra={
                            "url": sanitized_url,
                            "method": method,
                            "exception": type(exc).__name__,
                        },
                    )
                    raise

        # If somehow exits loop without returning
        if last_exc:
            raise last_exc
        raise httpx.RequestError("Request failed without response")

    @staticmethod
    def _extract_host(url: str) -> str:
        try:
            # fast parse
            prefix = "//"
            start = url.find(prefix)
            if start != -1:
                start += len(prefix)
                end = url.find("/", start)
                host = url[start:end] if end != -1 else url[start:]
                return host
        except Exception:  # nosec B110
            # Defensive: if parsing fails for any reason, return original URL
            # This is intentional fallback behavior, not an error condition
            pass
        return url
