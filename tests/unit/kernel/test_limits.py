"""
Tests for RateLimiter.
"""

import time
import pytest
from xcore.kernel.sandbox.limits import RateLimiter, RateLimitConfig, RateLimitExceeded, RateLimiterRegistry

def test_rate_limiter_success():
    config = RateLimitConfig(calls=5, period_seconds=1.0)
    limiter = RateLimiter(config)

    for _ in range(5):
        limiter.check("test")

    # Next one should fail
    with pytest.raises(RateLimitExceeded):
        limiter.check("test")

def test_rate_limiter_window_slide():
    config = RateLimitConfig(calls=2, period_seconds=0.1)
    limiter = RateLimiter(config)

    limiter.check("test")
    limiter.check("test")

    with pytest.raises(RateLimitExceeded):
        limiter.check("test")

    time.sleep(0.15)

    # Should be allowed again
    limiter.check("test")

def test_rate_limiter_stats():
    config = RateLimitConfig(calls=10, period_seconds=60.0)
    limiter = RateLimiter(config)

    limiter.check("test")
    limiter.check("test")

    stats = limiter.stats()
    assert stats["calls_in_window"] == 2
    assert stats["limit"] == 10
    assert stats["remaining"] == 8

def test_rate_limiter_registry():
    registry = RateLimiterRegistry()
    config = RateLimitConfig(calls=1, period_seconds=1.0)

    registry.register("p1", config)

    registry.check("p1") # ok
    with pytest.raises(RateLimitExceeded):
        registry.check("p1")

    # p2 has no limit registered, should pass
    registry.check("p2")
    registry.check("p2")

def test_rate_limiter_registry_stats():
    registry = RateLimiterRegistry()
    config = RateLimitConfig(calls=10, period_seconds=60.0)
    registry.register("p1", config)

    assert registry.stats("p2") is None
    assert registry.stats("p1")["limit"] == 10
