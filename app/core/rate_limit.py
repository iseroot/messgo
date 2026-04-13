from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic


class InMemoryRateLimiter:
    """Простой in-memory rate limiter по ключу."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """Проверяет, можно ли выполнить действие в окне времени."""

        now = monotonic()
        bucket = self._buckets[key]

        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True

    def reset(self) -> None:
        """Очищает состояние лимитера."""

        self._buckets.clear()
