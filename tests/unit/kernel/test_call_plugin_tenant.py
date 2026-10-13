"""call_plugin doit propager le tenant courant (ContextVar), pas ctx.tenant_id."""

import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from xcore.kernel.api.contract import TrustedBase
from xcore.kernel.runtime.supervisor import PluginSupervisor
from xcore.kernel.tenancy.services import _current_tenant_id


def _kernel_ctx(directory: str):
    ctx = MagicMock()
    ctx.config.tenancy = SimpleNamespace(
        enabled=True, default_tenant="default", enforce_ipc=False
    )
    ctx.config.directory = directory
    ctx.config.strict_trusted = False
    ctx.config.secret_key = b"test"
    ctx.services.as_dict.return_value = {}
    ctx.events.emit = AsyncMock()
    return ctx


class _Loader:
    def __init__(self, handlers):
        self._handlers = handlers

    def has(self, name):
        return name in self._handlers

    def get(self, name):
        return self._handlers[name]


class _Handler:
    def __init__(self, fn):
        self._fn = fn

    async def call(self, action, payload):
        return await self._fn(action, payload)


class _Plugin(TrustedBase):
    async def handle(self, action, payload):
        return {"status": "ok"}


async def _boot_supervisor(tmp: str) -> PluginSupervisor:
    sup = PluginSupervisor(_kernel_ctx(tmp))
    await sup.boot()
    return sup


async def test_nested_call_keeps_request_tenant():
    seen = {}
    with tempfile.TemporaryDirectory() as tmp:
        sup = await _boot_supervisor(tmp)

        plugin_a = _Plugin()
        # ctx.tenant_id figé à "default" comme au chargement du plugin
        plugin_a.ctx = SimpleNamespace(name="a", tenant_id="default", caller=sup.call)

        async def handle_a(action, payload):
            return await plugin_a.call_plugin("b", "ping")

        async def handle_b(action, payload):
            seen["tenant"] = _current_tenant_id.get()
            return {"status": "ok"}

        sup._permissions.grant_all("a")
        sup._permissions.grant_all("b")
        sup._loader = _Loader({"a": _Handler(handle_a), "b": _Handler(handle_b)})

        result = await sup.call("a", "run", {}, tenant_id="acme")

    assert result["status"] == "ok", result
    assert seen["tenant"] == "acme"


async def test_call_plugin_falls_back_to_ctx_tenant_without_contextvar():
    caller = AsyncMock(return_value={"status": "ok"})
    plugin = _Plugin()
    plugin.ctx = SimpleNamespace(name="a", tenant_id="static", caller=caller)

    await plugin.call_plugin("b", "ping")

    assert caller.await_args.kwargs["tenant_id"] == "static"
