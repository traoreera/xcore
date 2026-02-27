"""
Integration tests for plugin lifecycle.
"""

import tempfile
from pathlib import Path

import pytest

from xcore import Xcore


class TestPluginLifecycle:
    """Test full plugin lifecycle."""

    @pytest.fixture
    async def xcore_app(self):
        """Create XCore test instance."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create minimal config
            config_path = Path(tmp) / "test.yaml"
            config_path.write_text(
                """
app:
  name: test-app
  secret_key: test-secret-key-for-testing-min32chars

plugins:
  directory: ./plugins
  strict_trusted: false
  interval: 0

services:
  databases: {}
  cache:
    backend: memory
    ttl: 300
"""
            )

            app = Xcore(config_path=str(config_path))
            await app.boot()
            yield app
            await app.shutdown()

    @pytest.mark.asyncio
    async def test_xcore_boot(self, xcore_app):
        """Test XCore boots successfully."""
        assert xcore_app._booted is True
        assert xcore_app.services is not None
        assert xcore_app.plugins is not None
        assert xcore_app.events is not None

    @pytest.mark.asyncio
    async def test_services_available(self, xcore_app):
        """Test services are available after boot."""
        # Cache service should be available
        assert xcore_app.services.has("cache")

        cache = xcore_app.services.get("cache")
        assert cache is not None

    @pytest.mark.asyncio
    async def test_event_bus_working(self, xcore_app):
        """Test event bus is functional."""
        events = xcore_app.events

        received = []

        @events.on("test.event")
        async def handler(event):
            received.append(event.data)

        await events.emit("test.event", {"message": "hello"})
        import asyncio

        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0]["message"] == "hello"

    @pytest.mark.asyncio
    async def test_plugin_list_empty(self, xcore_app):
        """Test plugin list when no plugins loaded."""
        status = xcore_app.plugins.status()

        assert "plugins" in status
        assert status["count"] == 0

    @pytest.mark.asyncio
    async def test_health_check(self, xcore_app):
        """Test health check."""
        health = await xcore_app.services.health()

        assert "ok" in health
        assert "services" in health

    @pytest.mark.asyncio
    async def test_xcore_shutdown(self, xcore_app):
        """Test XCore shuts down cleanly."""
        assert xcore_app._booted is True

        await xcore_app.shutdown()

        assert xcore_app._booted is False

    @pytest.mark.asyncio
    async def test_multiple_shutdown_calls(self, xcore_app):
        """Test multiple shutdown calls are safe."""
        await xcore_app.shutdown()
        await xcore_app.shutdown()  # Should not raise

        assert xcore_app._booted is False
