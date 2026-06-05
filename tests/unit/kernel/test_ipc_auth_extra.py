"""Tests for IPCAuthMiddleware coverage gaps (wildcard, deny-by-default, etc.)."""

import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_loader(manifest=None):
    loader = MagicMock()
    loader.get_manifest.return_value = manifest
    return loader


class TestIPCAuthMiddlewareExtended:
    @pytest.mark.asyncio
    async def test_wildcard_allowed(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        manifest = MagicMock()
        manifest.allowed_callers = ["*"]
        loader = _make_loader(manifest)

        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("target", "action", {}, next_call, MagicMock(), caller="any_plugin")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_deny_by_default_empty_list(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        manifest = MagicMock()
        manifest.allowed_callers = []
        loader = _make_loader(manifest)

        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock()
        result = await mw("target", "action", {}, next_call, MagicMock(), caller="any_plugin")
        assert result["status"] == "error"
        assert result["code"] == "ipc_denied"
        next_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_caller_present_allowed(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        manifest = MagicMock()
        manifest.allowed_callers = ["billing", "crm"]
        loader = _make_loader(manifest)

        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("target", "action", {}, next_call, MagicMock(), caller="billing")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_caller_absent_denied(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        manifest = MagicMock()
        manifest.allowed_callers = ["billing"]
        loader = _make_loader(manifest)

        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock()
        result = await mw("target", "action", {}, next_call, MagicMock(), caller="unauthorized")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_invalid_allowed_callers_type(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        manifest = MagicMock()
        manifest.allowed_callers = "billing"  # not a list
        loader = _make_loader(manifest)

        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock()
        result = await mw("target", "action", {}, next_call, MagicMock(), caller="billing")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_virtual_plugin_always_allowed(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        loader = _make_loader(None)
        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("xcore", "plugin.list", {}, next_call, MagicMock(), caller="any")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_case_insensitive_caller(self):
        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
        manifest = MagicMock()
        manifest.allowed_callers = ["Billing"]
        loader = _make_loader(manifest)

        mw = IPCAuthMiddleware(loader, enforce=True)
        next_call = AsyncMock(return_value={"status": "ok"})
        result = await mw("target", "action", {}, next_call, MagicMock(), caller="billing")
        assert result["status"] == "ok"
