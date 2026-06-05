"""Tests for PermissionMiddleware, RateLimitMiddleware, MiddlewareRegistry."""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestPermissionMiddleware:
    @pytest.mark.asyncio
    async def test_permission_denied(self):
        from xcore.kernel.middlewares.permissions import PermissionMiddleware
        from xcore.kernel.permissions.engine import PermissionDenied

        perms = MagicMock()
        perms.check.side_effect = PermissionDenied("not allowed")
        mw = PermissionMiddleware(perms)

        next_call = AsyncMock()
        result = await mw("myplugin", "delete", {}, next_call, MagicMock())
        assert result["status"] == "error"
        assert result["code"] == "permission_denied"
        next_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_permission_allowed(self):
        from xcore.kernel.middlewares.permissions import PermissionMiddleware

        perms = MagicMock()
        perms.check.return_value = None  # no exception
        mw = PermissionMiddleware(perms)

        next_call = AsyncMock(return_value={"status": "ok"})
        handler = MagicMock()
        result = await mw("myplugin", "read", {}, next_call, handler)
        assert result["status"] == "ok"
        next_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_permission_with_resource_kwarg(self):
        from xcore.kernel.middlewares.permissions import PermissionMiddleware

        perms = MagicMock()
        mw = PermissionMiddleware(perms)
        next_call = AsyncMock(return_value={"status": "ok"})
        await mw("plugin", "action", {}, next_call, MagicMock(), resource="custom_resource")
        perms.check.assert_called_once_with("plugin", "custom_resource", "execute")


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        from xcore.kernel.middlewares.ratelimit import RateLimitMiddleware
        from xcore.kernel.sandbox.limits import RateLimitExceeded

        rate = MagicMock()
        rate.check.side_effect = RateLimitExceeded("too many")
        mw = RateLimitMiddleware(rate)

        next_call = AsyncMock()
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "error"
        assert result["code"] == "rate_limit_exceeded"
        next_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_ok(self):
        from xcore.kernel.middlewares.ratelimit import RateLimitMiddleware

        rate = MagicMock()
        rate.check.return_value = None
        mw = RateLimitMiddleware(rate)

        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("plugin", "action", {}, next_call, MagicMock())
        assert result["status"] == "ok"


class TestMiddlewareRegistry:
    def test_register_and_create_pipeline(self):
        from xcore.kernel.middlewares.middleware_registry import MiddlewareRegistry

        reg = MiddlewareRegistry()
        factory_called = []

        def my_factory(ctx):
            factory_called.append(ctx)
            mw = MagicMock()
            mw.__class__.__name__ = "MyMiddleware"
            return mw

        reg.register("my_mw", my_factory)
        pipeline = reg.create_pipeline(["my_mw"], {"key": "val"}, lambda: None)
        assert pipeline is not None
        assert len(factory_called) == 1

    def test_pipeline_missing_factory_logs_warning(self):
        from xcore.kernel.middlewares.middleware_registry import MiddlewareRegistry

        reg = MiddlewareRegistry()
        pipeline = reg.create_pipeline(["unknown_mw"], {}, lambda: None)
        assert pipeline is not None  # still returns pipeline, just empty

    def test_pipeline_factory_exception_logs_error(self):
        from xcore.kernel.middlewares.middleware_registry import MiddlewareRegistry

        reg = MiddlewareRegistry()

        def bad_factory(ctx):
            raise RuntimeError("boom")

        reg.register("bad", bad_factory)
        pipeline = reg.create_pipeline(["bad"], {}, lambda: None)
        assert pipeline is not None

    def test_register_overwrites(self):
        from xcore.kernel.middlewares.middleware_registry import MiddlewareRegistry

        reg = MiddlewareRegistry()
        calls = []
        reg.register("mw", lambda ctx: calls.append("first") or MagicMock())
        reg.register("mw", lambda ctx: calls.append("second") or MagicMock())
        reg.create_pipeline(["mw"], {}, lambda: None)
        assert "second" in calls
