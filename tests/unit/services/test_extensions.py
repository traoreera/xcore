"""Tests for ExtensionLoader."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from xcore.services.base import ServiceStatus
from xcore.services.extensions.loader import ExtensionLoader


class _FakeService:
    """Minimal service that looks like a BaseService."""
    def __init__(self, config=None):
        self._status = ServiceStatus.READY

    async def init(self):
        self._status = ServiceStatus.READY

    async def shutdown(self):
        self._status = ServiceStatus.STOPPED

    async def health_check(self):
        return True, "ok"

    def status(self):
        return {"name": "fake", "status": self._status.value}


class _BrokenService:
    def __init__(self, config=None):
        self._status = ServiceStatus.DEGRADED

    async def init(self):
        pass

    async def health_check(self):
        raise RuntimeError("broken")


class TestExtensionLoader:
    def test_init_empty_config(self):
        loader = ExtensionLoader({})
        assert loader.extensions == {}

    @pytest.mark.asyncio
    async def test_init_loads_extension(self):
        config = {
            "fake": {
                "module": "tests.unit.services.test_extensions:_FakeService",
                "config": {},
            }
        }
        loader = ExtensionLoader(config)
        await loader.init()
        assert "fake" in loader.extensions
        assert loader._status == ServiceStatus.READY

    @pytest.mark.asyncio
    async def test_init_no_extensions_degraded(self):
        loader = ExtensionLoader({})
        await loader.init()
        assert loader._status == ServiceStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_init_invalid_module_path(self):
        config = {"bad": {"module": "nonexistent.module:Class", "config": {}}}
        loader = ExtensionLoader(config)
        await loader.init()
        assert "bad" not in loader.extensions

    @pytest.mark.asyncio
    async def test_init_missing_module_key(self):
        config = {"bad": {}}
        loader = ExtensionLoader(config)
        await loader.init()
        assert "bad" not in loader.extensions

    @pytest.mark.asyncio
    async def test_shutdown_calls_shutdown(self):
        config = {
            "fake": {
                "module": "tests.unit.services.test_extensions:_FakeService",
                "config": {},
            }
        }
        loader = ExtensionLoader(config)
        await loader.init()
        await loader.shutdown()
        assert loader.extensions == {}
        assert loader._status == ServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_health_check_no_extensions(self):
        loader = ExtensionLoader({})
        ok, msg = await loader.health_check()
        assert ok is True
        assert "no extensions" in msg

    @pytest.mark.asyncio
    async def test_health_check_all_ok(self):
        config = {
            "fake": {
                "module": "tests.unit.services.test_extensions:_FakeService",
                "config": {},
            }
        }
        loader = ExtensionLoader(config)
        await loader.init()
        ok, msg = await loader.health_check()
        assert ok is True

    @pytest.mark.asyncio
    async def test_health_check_broken_extension(self):
        config = {
            "broken": {
                "module": "tests.unit.services.test_extensions:_BrokenService",
                "config": {},
            }
        }
        loader = ExtensionLoader(config)
        await loader.init()
        # manually insert broken service since it won't be READY
        from xcore.services.base import ServiceStatus
        b = _BrokenService()
        b._status = ServiceStatus.READY
        loader.extensions["broken"] = b
        ok, msg = await loader.health_check()
        assert ok is False
        assert "broken" in msg

    def test_status(self):
        loader = ExtensionLoader({})
        s = loader.status()
        assert s["name"] == "extensions"
        assert "status" in s
        assert "extensions" in s

    def test_load_no_module_field_raises(self):
        loader = ExtensionLoader({})
        with pytest.raises(ValueError, match="module"):
            loader._load("ext", {})

    def test_load_invalid_format_raises(self):
        loader = ExtensionLoader({})
        with pytest.raises(ValueError, match="format"):
            loader._load("ext", {"module": "no_colon_here"})

    def test_load_with_kwargs(self):
        """Test that if cls(config=…) fails, it falls back to cls(**config) or cls()."""
        import sys
        import types

        mod = types.ModuleType("_test_ext_module")

        class NoConfigKwarg:
            def __init__(self, host="localhost", port=80):
                self._status = ServiceStatus.READY

        mod.NoConfigKwarg = NoConfigKwarg
        sys.modules["_test_ext_module"] = mod

        loader = ExtensionLoader({})
        result = loader._load("ext", {
            "module": "_test_ext_module:NoConfigKwarg",
            "config": {"host": "myhost", "port": 9090},
        })
        assert result._status == ServiceStatus.READY
