
import time
import pytest
from xcore.kernel.sandbox.limits import RateLimiter, RateLimitConfig, RateLimiterRegistry, RateLimitExceeded

def test_ratelimiter_basic():
    config = RateLimitConfig(calls=2, period_seconds=1.0)
    limiter = RateLimiter(config)

    # Should allow 2 calls
    limiter.check("plugin1")
    limiter.check("plugin1")

    # Should raise for 3rd call
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("plugin1")
    assert "quota dépassé" in str(exc.value)

def test_ratelimiter_expiry():
    config = RateLimitConfig(calls=1, period_seconds=0.1)
    limiter = RateLimiter(config)

    limiter.check("plugin1")

    # Wait for expiry
    time.sleep(0.15)

    # Should be allowed again
    limiter.check("plugin1")

def test_registry():
    registry = RateLimiterRegistry()
    config = RateLimitConfig(calls=1, period_seconds=60.0)
    registry.register("plugin1", config)

    registry.check("plugin1")
    with pytest.raises(RateLimitExceeded):
        registry.check("plugin1")

    # plugin2 should have no limit by default or allow if not registered
    registry.check("plugin2")
    registry.check("plugin2")
