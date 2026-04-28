"""
Tests for LifecycleManager.
"""

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from xcore.kernel.api.contract import BasePlugin, ExecutionMode
from xcore.kernel.runtime.lifecycle import LifecycleManager, LoadError
from xcore.kernel.runtime.state_machine import PluginState
from xcore.sdk.plugin_base import PluginManifest


# Mock plugin classes for testing
class MockPlugin(BasePlugin):
    """Mock plugin implementing BasePlugin."""

    def __init__(self):
        self._services = {}
        self.ctx = None
        self.on_load_called = False
        self.on_reload_called = False
        self.on_unload_called = False

    async def handle(self, action: str, payload: dict) -> dict:
        return {"status": "ok", "action": action}

    async def on_load(self):
        self.on_load_called = True

    async def on_reload(self):
        self.on_reload_called = True

    async def on_unload(self):
        self.on_unload_called = True

    async def _inject_context(self, ctx):
        self.ctx = ctx


class MockPluginWithRouter(MockPlugin):
    """Mock plugin with custom router."""

    def get_router(self):
        router = MagicMock()
        router.routes = [MagicMock(), MagicMock()]
        return router


class MockPluginNoHandle:
    """Mock plugin that doesn't implement handle."""


class MockPluginRaisesOnLoad(BasePlugin):
    """Mock plugin that raises in on_load."""

    async def handle(self, action: str, payload: dict) -> dict:
        return {"status": "ok"}

    async def on_load(self):
        raise RuntimeError("Load failed")


class MockPluginWithServices(BasePlugin):
    """Mock plugin that registers services."""

    def __init__(self):
        super().__init__()
        self._services = {"custom_service": "value"}

    async def handle(self, action: str, payload: dict) -> dict:
        return {"status": "ok"}


@pytest.fixture
def mock_manifest(tmp_path):
    """Create a mock manifest."""
    from types import SimpleNamespace

    manifest = MagicMock(spec=PluginManifest)
    manifest.name = "test_plugin"
    manifest.entry_point = "src/main.py"
    # Create resources as a SimpleNamespace object
    manifest.resources = SimpleNamespace(timeout_seconds=10)
    manifest.env = {}
    manifest.plugin_dir = tmp_path
    return manifest


@pytest.fixture
def shared_services():
    """Create a shared services dict."""
    return {}


@pytest.fixture
def lifecycle_manager(mock_manifest, shared_services):
    """Create a LifecycleManager instance."""
    from xcore.kernel.context import KernelContext

    ctx = KernelContext(
        config=MagicMock(),
        services=MagicMock(),
        events=MagicMock(),
        hooks=MagicMock(),
        registry=MagicMock(),
        metrics=MagicMock(),
        tracer=MagicMock(),
        health=MagicMock(),
    )
    ctx.services.as_dict.return_value = shared_services
    return LifecycleManager(
        manifest=mock_manifest,
        ctx=ctx,
    )


class TestLifecycleManager:
    """Test LifecycleManager functionality."""

    def test_initial_state(self, lifecycle_manager):
        """Test initial state of lifecycle manager."""
        assert lifecycle_manager.state == PluginState.UNLOADED
        assert lifecycle_manager.is_ready is False
        assert lifecycle_manager.uptime is None
        assert lifecycle_manager._instance is None
        assert lifecycle_manager._module is None

    @pytest.mark.asyncio
    async def test_load_missing_entry_point(self, lifecycle_manager):
        """Test load raises error when entry point doesn't exist."""
        with pytest.raises(LoadError) as exc_info:
            await lifecycle_manager.load()

        assert "Not found entry point" in str(exc_info.value)
        assert lifecycle_manager.state == PluginState.FAILED

    @pytest.mark.asyncio
    async def test_load_missing_plugin_class(self, lifecycle_manager, tmp_path):
        """Test load raises error when Plugin class not found."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# No Plugin class")

        with pytest.raises(LoadError) as exc_info:
            await lifecycle_manager.load()

        assert "class Plugin() not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_invalid_plugin_contract(self, lifecycle_manager, tmp_path):
        """Test load raises error when plugin doesn't implement BasePlugin."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
class Plugin:
    def __init__(self):
        pass
"""
        )

        with pytest.raises(LoadError) as exc_info:
            await lifecycle_manager.load()

        assert "not respect contrat BasePlugin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_success(self, lifecycle_manager, tmp_path):
        """Test successful plugin load."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}

    async def on_load(self):
        self.loaded = True
"""
        )

        await lifecycle_manager.load()

        assert lifecycle_manager.state == PluginState.READY
        assert lifecycle_manager.is_ready is True
        assert lifecycle_manager._instance is not None
        assert lifecycle_manager.uptime is not None

    @pytest.mark.asyncio
    async def test_load_calls_on_load(self, lifecycle_manager, tmp_path):
        """Test that on_load hook is called."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    def __init__(self):
        self.on_load_called = False

    async def handle(self, action, payload):
        return {"status": "ok"}

    async def on_load(self):
        self.on_load_called = True
"""
        )

        await lifecycle_manager.load()
        assert lifecycle_manager._instance.on_load_called is True

    @pytest.mark.asyncio
    async def test_call_action(self, lifecycle_manager, tmp_path):
        """Test calling an action on the plugin."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok", "action": action}
"""
        )

        await lifecycle_manager.load()
        result = await lifecycle_manager.call("test_action", {"key": "value"})

        assert result["status"] == "ok"
        assert result["action"] == "test_action"

    @pytest.mark.asyncio
    async def test_call_not_loaded(self, lifecycle_manager):
        """Test call raises error when plugin not loaded."""
        with pytest.raises(RuntimeError) as exc_info:
            await lifecycle_manager.call("action", {})

        assert "not loaded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_timeout(self, lifecycle_manager, tmp_path):
        """Test call handles timeout."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
import asyncio
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        await asyncio.sleep(10)  # Longer than timeout
        return {"status": "ok"}
"""
        )

        lifecycle_manager.manifest.resources.timeout_seconds = 0.1
        await lifecycle_manager.load()
        result = await lifecycle_manager.call("action", {})

        assert result["status"] == "error"
        assert "timeout" in result["code"].lower()

    @pytest.mark.asyncio
    async def test_concurrent_calls(self, lifecycle_manager, tmp_path):
        """Test that multiple calls can be made concurrently."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
import asyncio
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        await asyncio.sleep(0.1)
        return {"status": "ok", "action": action}
"""
        )

        lifecycle_manager.manifest.resources.timeout_seconds = 1
        await lifecycle_manager.load()

        results = await asyncio.gather(
            lifecycle_manager.call("ping1", {}), lifecycle_manager.call("ping2", {})
        )

        assert len(results) == 2
        assert results[0]["action"] == "ping1"
        assert results[1]["action"] == "ping2"

    @pytest.mark.asyncio
    async def test_reload(self, lifecycle_manager, tmp_path):
        """Test plugin reload."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}

    async def on_reload(self):
        self.reloaded = True
"""
        )

        await lifecycle_manager.load()
        first_instance = lifecycle_manager._instance

        await lifecycle_manager.reload()

        assert lifecycle_manager.state == PluginState.READY
        assert lifecycle_manager._instance is not first_instance

    @pytest.mark.asyncio
    async def test_unload(self, lifecycle_manager, tmp_path):
        """Test plugin unload."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}

    async def on_unload(self):
        self.unloaded = True
"""
        )

        await lifecycle_manager.load()
        await lifecycle_manager.unload()

        assert lifecycle_manager._instance is None
        assert lifecycle_manager.state == PluginState.UNLOADED

    @pytest.mark.asyncio
    async def test_collect_router(self, lifecycle_manager, tmp_path):
        """Test router collection."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin
from unittest.mock import MagicMock

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}

    def get_router(self):
        router = MagicMock()
        router.routes = [1, 2, 3]
        return router
"""
        )

        await lifecycle_manager.load()
        assert lifecycle_manager.plugin_router is not None

    def test_status_not_loaded(self, lifecycle_manager):
        """Test status when plugin not loaded."""
        status = lifecycle_manager.status()

        assert status["name"] == "test_plugin"
        assert status["mode"] == "trusted"
        assert status["state"] == "unloaded"
        assert status["loaded"] is False
        assert status["uptime"] is None

    @pytest.mark.asyncio
    async def test_status_loaded(self, lifecycle_manager, tmp_path):
        """Test status when plugin is loaded."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}
"""
        )

        await lifecycle_manager.load()
        status = lifecycle_manager.status()

        assert status["loaded"] is True
        assert status["state"] == "ready"
        assert status["uptime"] is not None

    def test_propagate_services_no_instance(self, lifecycle_manager):
        """Test propagate_services when no instance."""
        result = lifecycle_manager.propagate_services()
        assert result == lifecycle_manager._services

    '''    @pytest.mark.asyncio
    async def test_propagate_services_new_keys(self, lifecycle_manager, tmp_path):
        """Test propagate_services adds new keys."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("""
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    def __init__(self):
        super().__init__()

    async def on_load(self,):
        self._services = {"new_service": "value"}
    async def handle(self, action, payload):
        return {"status": "ok"}
""")

        shared = {}
        lifecycle_manager._services = shared

        await lifecycle_manager.load()
        lifecycle_manager.propagate_services(is_reload=False)
        shared |= lifecycle_manager._services
        assert "new_service" in shared

    @pytest.mark.asyncio
    async def test_propagate_services_reload(self, lifecycle_manager, tmp_path):
        """Test propagate_services updates keys on reload."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("""
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self._services = {"service": "new_value"}

    async def handle(self, action, payload):
        return {"status": "ok"}
""")

        shared = {"service": "old_value"}
        lifecycle_manager._services = shared

        await lifecycle_manager.load()
        lifecycle_manager.propagate_services(is_reload=True)

        assert shared["service"] == "new_value"
    '''

    def test_instantiate_with_services(self, lifecycle_manager):
        """Test _instantiate with services injection."""

        class PluginWithServicesArg:
            def __init__(self, services=None):
                self.services = services

        instance = lifecycle_manager._instantiate(PluginWithServicesArg)
        assert instance.services == lifecycle_manager._services

    def test_instantiate_without_services_arg(self, lifecycle_manager):
        """Test _instantiate without services argument."""

        class PluginNoServicesArg:
            def __init__(self):
                self._services = {}

        lifecycle_manager._instantiate(PluginNoServicesArg)
        # Should inject services via attribute

    def test_import_module(self, lifecycle_manager, tmp_path):
        """Test _import_module."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("test_var = 'hello'")

        module = lifecycle_manager._import_module("test_module_import", test_file)
        assert module.test_var == "hello"

    def test_on_state_change(self, lifecycle_manager):
        """Test state change callback."""
        lifecycle_manager._events = MagicMock()
        lifecycle_manager._on_state_change(PluginState.UNLOADED, PluginState.LOADING)

        lifecycle_manager._events.emit_sync.assert_called_once()
        call_args = lifecycle_manager._events.emit_sync.call_args
        assert "state_changed" in call_args[0][0]


class TestLifecycleManagerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_call_non_dict_result(self, lifecycle_manager, tmp_path):
        """Test call handles non-dict result."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return "string_result"  # Not a dict
"""
        )

        await lifecycle_manager.load()
        result = await lifecycle_manager.call("action", {})

        assert result["status"] == "ok"
        assert result["result"] == "string_result"

    '''
    @pytest.mark.asyncio
    async def test_load_with_env_injection(self, lifecycle_manager, tmp_path):
        """Test load with environment variable injection."""
        lifecycle_manager.manifest.env = {"TEST_KEY": "test_value"}

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("""
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}
""")

        await lifecycle_manager.load()
        assert lifecycle_manager._instance.ctx.env["TEST_KEY"] == "test_value"
    '''

    @pytest.mark.asyncio
    async def test_unload_cleans_modules(self, lifecycle_manager, tmp_path):
        """Test unload cleans sys.modules."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            """
from xcore.kernel.api.contract import BasePlugin

class Plugin(BasePlugin):
    async def handle(self, action, payload):
        return {"status": "ok"}
"""
        )

        await lifecycle_manager.load()
        module_name = f"xcore_plugin_{lifecycle_manager.manifest.name}"
        assert module_name in sys.modules or f"{module_name}.main" in sys.modules

        await lifecycle_manager.unload()

        # Check modules are cleaned up
        assert module_name not in sys.modules
        assert f"{module_name}.main" not in sys.modules
