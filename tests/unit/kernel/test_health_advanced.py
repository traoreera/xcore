
import asyncio
import pytest
from xcore.kernel.observability.health import HealthChecker, HealthStatus

@pytest.mark.asyncio
async def test_health_checker_liveness_readiness():
    hc = HealthChecker()

    @hc.register("db", kind="readiness")
    async def check_db():
        return True, "connected"

    @hc.register("disk", kind="liveness")
    def check_disk():
        return True, "ok"

    # Test all
    report = await hc.run_all()
    assert report["status"] == "healthy"
    assert "db" in report["checks"]
    assert "disk" in report["checks"]
    assert "process" in report["checks"] # default

    # Test liveness only
    live_report = await hc.run_liveness()
    assert "disk" in live_report["checks"]
    assert "process" in live_report["checks"]
    assert "db" not in live_report["checks"]

    # Test readiness only
    ready_report = await hc.run_readiness()
    assert "db" in ready_report["checks"]
    assert "disk" not in ready_report["checks"]

@pytest.mark.asyncio
async def test_health_checker_unhealthy():
    hc = HealthChecker()

    @hc.register("fail", kind="readiness")
    async def check_fail():
        return False, "error"

    report = await hc.run_readiness()
    assert report["status"] == "degraded"
    assert report["checks"]["fail"]["status"] == "degraded"
