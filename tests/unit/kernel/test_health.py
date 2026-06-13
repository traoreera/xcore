"""Tests for HealthChecker."""

import pytest
import asyncio

from xcore.kernel.observability.health import HealthChecker, HealthStatus, CheckResult


class TestHealthChecker:
    @pytest.mark.asyncio
    async def test_run_all_empty(self):
        hc = HealthChecker()
        result = await hc.run_all()
        assert result["status"] == "healthy"
        # HealthChecker auto-registers process + event_loop liveness checks
        assert "process" in result["checks"]
        assert "event_loop" in result["checks"]

    @pytest.mark.asyncio
    async def test_register_and_run_async(self):
        hc = HealthChecker()

        @hc.register("database")
        async def check_db():
            return True, "ok"

        result = await hc.run_all()
        assert result["status"] == "healthy"
        assert result["checks"]["database"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_register_and_run_sync(self):
        hc = HealthChecker()

        @hc.register("cache")
        def check_cache():
            return True, "ok"

        result = await hc.run_all()
        assert result["status"] == "healthy"
        assert result["checks"]["cache"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_degraded_check(self):
        hc = HealthChecker()

        @hc.register("cache")
        async def check_cache():
            return False, "connection lost"

        result = await hc.run_all()
        assert result["status"] == "degraded"
        assert result["checks"]["cache"]["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_unhealthy_check_on_exception(self):
        hc = HealthChecker()

        @hc.register("db")
        async def check_db():
            raise RuntimeError("DB crashed")

        result = await hc.run_all()
        assert result["status"] == "unhealthy"
        assert result["checks"]["db"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_unhealthy_on_timeout(self):
        hc = HealthChecker()

        @hc.register("slow")
        async def slow_check():
            await asyncio.sleep(10)
            return True, "ok"

        result = await hc.run_all(timeout=0.01)
        assert result["checks"]["slow"]["status"] == "unhealthy"
        assert "timeout" in result["checks"]["slow"]["message"].lower()

    @pytest.mark.asyncio
    async def test_overall_unhealthy_takes_priority_over_degraded(self):
        hc = HealthChecker()

        @hc.register("degraded")
        async def degraded():
            return False, "degraded"

        @hc.register("unhealthy")
        async def unhealthy():
            raise RuntimeError("crash")

        result = await hc.run_all()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_duration_ms_present(self):
        hc = HealthChecker()

        @hc.register("db")
        async def check_db():
            return True, "ok"

        result = await hc.run_all()
        assert isinstance(result["checks"]["db"]["duration_ms"], float)

    def test_check_result_dataclass(self):
        cr = CheckResult(name="db", status=HealthStatus.HEALTHY, message="ok", duration_ms=1.5)
        assert cr.name == "db"
        assert cr.status == HealthStatus.HEALTHY


class TestHealthStatus:
    def test_values(self):
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
