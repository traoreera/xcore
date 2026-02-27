"""
Integration tests for XCore framework.
"""

import tempfile

import pytest

from xcore import Xcore


class TestXcoreBoot:
    """Test Xcore boot and shutdown."""

    @pytest.fixture
    def minimal_config(self):
        """Create minimal configuration file."""
        config_content = """
app:
  name: test-app
  secret_key: test-secret-key-32-chars-long!!!

plugins:
  directory: ./plugins

services:
  databases: {}
  cache:
    backend: memory
    ttl: 300
    max_size: 1000
  scheduler:
    enabled: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            return f.name

    @pytest.mark.asyncio
    async def test_boot_and_shutdown(self, minimal_config):
        """Test basic boot and shutdown."""
        xcore = Xcore(config_path=minimal_config)

        try:
            await xcore.boot()

            assert xcore._booted is True
            assert xcore.services is not None
            assert xcore.events is not None
            assert xcore.hooks is not None
            assert xcore.registry is not None

        finally:
            await xcore.shutdown()

        assert xcore._booted is False

    @pytest.mark.asyncio
    async def test_double_boot(self, minimal_config):
        """Test double boot is safe."""
        xcore = Xcore(config_path=minimal_config)

        try:
            await xcore.boot()
            # Second boot should be safe
            await xcore.boot()
            assert xcore._booted is True
        finally:
            await xcore.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_without_boot(self, minimal_config):
        """Test shutdown without boot is safe."""
        xcore = Xcore(config_path=minimal_config)

        # Should not raise
        await xcore.shutdown()

    @pytest.mark.asyncio
    async def test_service_access(self, minimal_config):
        """Test service access after boot."""
        xcore = Xcore(config_path=minimal_config)

        try:
            await xcore.boot()

            # Check services
            assert xcore.services.has("cache")
            cache = xcore.services.get("cache")
            assert cache is not None

        finally:
            await xcore.shutdown()


class TestPluginLoading:
    """Test plugin loading."""

    @pytest.fixture
    def config_with_plugins(self, tmp_path):
        """Create configuration with plugin directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create test plugin
        test_plugin = plugins_dir / "test_plugin"
        test_plugin.mkdir()
        src_dir = test_plugin / "src"
        src_dir.mkdir()

        # plugin.yaml
        (test_plugin / "plugin.yaml").write_text(
            """
name: test_plugin
version: 1.0.0
execution_mode: trusted
"""
        )

        # main.py
        (src_dir / "main.py").write_text(
            """
from xcore.sdk import TrustedBase, ok

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        return ok(message="pong")
"""
        )

        config_content = f"""
app:
  name: test-app
  secret_key: test-secret-key-32-chars-long!!!

plugins:
  directory: {plugins_dir}

services:
  databases: {{}}
  cache:
    backend: memory
    ttl: 300
"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(config_content)

        return str(config_path)

    @pytest.mark.asyncio
    async def test_plugin_loaded(self, config_with_plugins):
        """Test plugin is loaded."""
        xcore = Xcore(config_path=config_with_plugins)

        try:
            await xcore.boot()

            # Plugin should be loaded
            plugins = xcore.plugins.list_plugins()
            assert "test_plugin" in plugins

        finally:
            await xcore.shutdown()

    @pytest.mark.asyncio
    async def test_plugin_call(self, config_with_plugins):
        """Test calling plugin action."""
        xcore = Xcore(config_path=config_with_plugins)

        try:
            await xcore.boot()

            result = await xcore.plugins.call("test_plugin", "ping", {})

            assert result["status"] == "ok"

        finally:
            await xcore.shutdown()


class TestEventSystem:
    """Test event system integration."""

    @pytest.fixture
    def minimal_config(self):
        """Create minimal configuration."""
        config_content = """
app:
  name: test-app
  secret_key: test-secret-key-32-chars-long!!!

plugins:
  directory: ./plugins

services:
  databases: {}
  cache:
    backend: memory
    ttl: 300
  scheduler:
    enabled: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            return f.name

    @pytest.mark.asyncio
    async def test_event_emit_and_receive(self, minimal_config):
        """Test event emission and receiving."""
        xcore = Xcore(config_path=minimal_config)

        try:
            await xcore.boot()

            received = []

            @xcore.events.on("test.event")
            async def handler(event):
                received.append(event.data)

            await xcore.events.emit("test.event", {"message": "hello"})

            import asyncio

            await asyncio.sleep(0.1)

            assert len(received) == 1
            assert received[0]["message"] == "hello"

        finally:
            await xcore.shutdown()

    @pytest.mark.asyncio
    async def test_system_event_emitted(self, minimal_config):
        """Test system events are emitted."""
        xcore = Xcore(config_path=minimal_config)

        received = []

        @xcore.events.on("xcore.plugins.booted")
        async def handler(event):
            received.append(event)

        try:
            await xcore.boot()
            import asyncio

            await asyncio.sleep(0.1)

            assert len(received) == 1

        finally:
            await xcore.shutdown()
