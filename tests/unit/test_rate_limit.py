from app.core.rate_limit import InMemoryRateLimiter


def test_rate_limit_allows_until_limit():
    limiter = InMemoryRateLimiter()
    assert limiter.allow("k", limit=2, window_seconds=60)
    assert limiter.allow("k", limit=2, window_seconds=60)
    assert not limiter.allow("k", limit=2, window_seconds=60)


def test_rate_limit_isolated_by_key():
    limiter = InMemoryRateLimiter()
    assert limiter.allow("k1", limit=1, window_seconds=60)
    assert limiter.allow("k2", limit=1, window_seconds=60)
