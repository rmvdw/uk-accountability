"""Polite HTTP for adapters: one download per URL per run, and backoff on rate limits.

Several indicators often share one publisher file (three ONS indicators read the
same workbook), so responses are cached for the life of the process. A refresh is
one process, so each file is fetched once per refresh.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request

USER_AGENT = "uk-accountability (+https://github.com/rmvdw/uk-accountability)"
MAX_ATTEMPTS = 4
MAX_WAIT = 90  # seconds, per retry

_cache: dict[str, bytes] = {}


def _wait_seconds(exc: urllib.error.HTTPError, attempt: int) -> float:
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after and retry_after.strip().isdigit():
        return min(float(retry_after), MAX_WAIT)
    return min(15.0 * 2 ** (attempt - 1), MAX_WAIT)


def get(url: str, timeout: int = 120, sleep=time.sleep) -> bytes:
    if url in _cache:
        return _cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            _cache[url] = data
            return data
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if not retryable or attempt == MAX_ATTEMPTS:
                raise
            sleep(_wait_seconds(exc, attempt))
    raise RuntimeError("unreachable")


def clear_cache() -> None:
    _cache.clear()
