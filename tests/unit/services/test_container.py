"""
Tests for ServiceContainer.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from xcore.services.base import BaseService, BaseServiceProvider, ServiceStatus
from xcore.services.container import (
    CacheServiceProvider,
    DatabaseServiceProvider,
    ExtensionServiceProvider,
    SchedulerServiceProvider,
    ServiceContainer,
)


# Mock service classes for testing
class MockService(BaseService):
    """Mock service for testing."""

    name = "mock_service"

    def __init__(self):
        super().__init__()
        self.init_called = False
        self.shutdown_called = False

    async def init(self) -> None:
        self.init_called = True
        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        self.shutdown_called = True
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        return True, "OK"

    def status(self) -> dict[str, Any]:
        return {"name": self.name, "status": self._status.value}


@dataclass
class MockConfig:
    """Mock configuration for ServiceContainer."""

    databases: dict = None
    cache: Any = None
    scheduler: Any = None
    extensions: dict = None

    def __post_init__(self):
        if self.databases is None:
            self.databases = {}
        if self.extensions is None:
            self.extensions = {}


class TestServiceContainer:
    """Test ServiceContainer functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return MockConfig()

    @pytest.fixture
    def container(self, mock_config):
        """Create fresh ServiceContainer."""
        return ServiceContainer(mock_config)

    def test_default_providers_present(self):
        """Test default providers are present."""
        assert len(ServiceContainer.DEFAULT_PROVIDERS) == 4
        assert DatabaseServiceProvider in ServiceContainer.DEFAULT_PROVIDERS
        assert CacheServiceProvider in ServiceContainer.DEFAULT_PROVIDERS
        assert SchedulerServiceProvider in ServiceContainer.DEFAULT_PROVIDERS
        assert ExtensionServiceProvider in ServiceContainer.DEFAULT_PROVIDERS

    def test_get_nonexistent_service(self, container):
        """Test getting nonexistent service raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            container.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "indisponible" in str(exc_info.value)

    def test_get_or_none_nonexistent(self, container):
        """Test get_or_none returns None for nonexistent service."""
        assert container.get_or_none("nonexistent") is None

    def test_has_service(self, container):
        """Test has() method."""
        assert container.has("test") is False

        # Manually add a service
        container._raw["test"] = MockService()
        assert container.has("test") is True

    def test_has_after_removal(self, container):
        """Test has() after service removal."""
        container._raw["test"] = MockService()
        assert container.has("test") is True

        del container._raw["test"]
        assert container.has("test") is False

    def test_as_dict(self, container):
        """Test as_dict() returns internal dict."""
        service = MockService()
        container._raw["test"] = service

        result = container.as_dict()
        assert result["test"] is service

    def test_get_existing_service(self, container):
        """Test getting existing service."""
        service = MockService()
        container._raw["test_service"] = service

        result = container.get("test_service")
        assert result is service

    def test_get_as_correct_type(self, container):
        """Test get_as() with correct type."""
        service = MockService()
        container._raw["test_service"] = service

        result = container.get_as("test_service", MockService)
        assert result is service

    def test_get_as_wrong_type(self, container):
        """Test get_as() with wrong type raises TypeError."""
        service = MockService()
        container._raw["test_service"] = service

        with pytest.raises(TypeError) as exc_info:
            container.get_as("test_service", str)

        assert "MockService" in str(exc_info.value)
        assert "str" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_init_with_custom_providers(self, container):
        """Test init with custom providers."""
        mock_provider = AsyncMock(spec=BaseServiceProvider)

        await container.init(providers=[mock_provider])

        mock_provider.init.assert_called_once_with(container)

    @pytest.mark.asyncio
    async def test_shutdown_empty(self, container):
        """Test shutdown with no services."""
        await container.shutdown()
        assert len(container._services) == 0
        assert len(container._raw) == 0

    @pytest.mark.asyncio
    async def test_shutdown_with_services(self, container):
        """Test shutdown calls shutdown on all services."""
        service1 = MockService()
        service2 = MockService()

        container._services["service1"] = service1
        container._services["service2"] = service2
        container._raw["service1"] = service1
        container._raw["service2"] = service2

        await container.shutdown()

        assert service1.shutdown_called is True
        assert service2.shutdown_called is True
        assert len(container._services) == 0
        assert len(container._raw) == 0

    @pytest.mark.asyncio
    async def test_shutdown_timeout(self, container):
        """Test shutdown with timeout."""
        slow_service = MockService()
        slow_service.shutdown = AsyncMock(side_effect=asyncio.TimeoutError)

        container._services["slow"] = slow_service
        container._raw["slow"] = slow_service

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            await container.shutdown()

    @pytest.mark.asyncio
    async def test_health_empty(self, container):
        """Test health check with no services."""
        result = await container.health()
        assert result["ok"] is True
        assert result["services"] == {}

    @pytest.mark.asyncio
    async def test_health_with_services(self, container):
        """Test health check with services."""
        service = MockService()
        container._services["test"] = service

        result = await container.health()
        assert result["ok"] is True
        assert result["services"]["test"]["ok"] is True
        assert result["services"]["test"]["msg"] == "OK"

    @pytest.mark.asyncio
    async def test_health_with_failing_service(self, container):
        """Test health check with failing service."""
        service = MockService()
        service.health_check = AsyncMock(return_value=(False, "Connection failed"))
        container._services["test"] = service

        result = await container.health()
        assert result["ok"] is False
        assert result["services"]["test"]["ok"] is False
        assert result["services"]["test"]["msg"] == "Connection failed"

    @pytest.mark.asyncio
    async def test_health_exception(self, container):
        """Test health check when service raises exception."""
        service = MockService()
        service.health_check = AsyncMock(side_effect=Exception("Health check failed"))
        container._services["test"] = service

        result = await container.health()
        assert result["ok"] is False
        assert "Health check failed" in result["services"]["test"]["msg"]

    def test_status_empty(self, container):
        """Test status with no services."""
        result = container.status()
        assert result["services"] == {}
        assert result["registered_keys"] == []

    def test_status_with_services(self, container):
        """Test status with services."""
        service = MockService()
        container._services["test"] = service
        container._raw["service1"] = service
        container._raw["service2"] = service

        result = container.status()
        assert "test" in result["services"]
        assert sorted(result["registered_keys"]) == ["service1", "service2"]


class TestServiceProviders:
    """Test individual service providers."""

    @pytest.mark.asyncio
    async def test_cache_provider(self):
        @dataclass
        class CacheConfig:
            backend: str = "memory"

        config = MockConfig(cache=CacheConfig())
        container = ServiceContainer(config)
        provider = CacheServiceProvider()

        with patch("xcore.services.cache.service.CacheService") as mock_cache_class:
            mock_svc = MockService()
            mock_cache_class.return_value = mock_svc

            await provider.init(container)

            mock_cache_class.assert_called_once()
            assert container.get("cache") is mock_svc

    @pytest.mark.asyncio
    async def test_database_provider_empty(self):
        config = MockConfig(databases={})
        container = ServiceContainer(config)
        provider = DatabaseServiceProvider()

        await provider.init(container)
        assert "database" not in container._services
