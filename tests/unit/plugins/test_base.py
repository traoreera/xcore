"""
Tests for plugin base classes and SDK.
"""


import pytest

from xcore.kernel.api.contract import ExecutionMode
from xcore.sdk.plugin_base import (
    PluginManifest,
    RateLimitConfig,
    ResourceConfig,
    RuntimeConfig,
)


class TestRateLimitConfig:
    """Test RateLimitConfig."""

    def test_default_values(self):
        """Test default rate limit values."""
        config = RateLimitConfig()

        assert config.calls == 100
        assert config.period_seconds == 60

    def test_custom_values(self):
        """Test custom rate limit values."""
        config = RateLimitConfig(calls=500, period_seconds=30)

        assert config.calls == 500
        assert config.period_seconds == 30


class TestResourceConfig:
    """Test ResourceConfig."""

    def test_default_values(self):
        """Test default resource values."""
        config = ResourceConfig()

        assert config.timeout_seconds == 10
        assert config.max_memory_mb == 128
        assert config.max_disk_mb == 50
        assert isinstance(config.rate_limit, RateLimitConfig)

    def test_custom_values(self):
        """Test custom resource values."""
        config = ResourceConfig(
            timeout_seconds=30,
            max_memory_mb=512,
            max_disk_mb=200,
            rate_limit=RateLimitConfig(calls=1000, period_seconds=60),
        )

        assert config.timeout_seconds == 30
        assert config.max_memory_mb == 512
        assert config.max_disk_mb == 200
        assert config.rate_limit.calls == 1000


class TestRuntimeConfig:
    """Test RuntimeConfig."""

    def test_default_values(self):
        """Test default runtime values."""
        config = RuntimeConfig()

        assert config.health_check.enabled is True
        assert config.health_check.interval_seconds == 30
        assert config.health_check.timeout_seconds == 3
        assert config.retry.max_attempts == 1
        assert config.retry.backoff_seconds == 0.0


class TestPluginManifest:
    """Test PluginManifest."""

    def test_minimal_manifest(self, tmp_path):
        """Test creating minimal manifest."""
        manifest = PluginManifest(
            name="test_plugin", version="1.0.0", plugin_dir=tmp_path
        )

        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.execution_mode == ExecutionMode.LEGACY

    def test_full_manifest(self, tmp_path):
        """Test creating full manifest."""
        manifest = PluginManifest(
            name="test_plugin",
            version="2.0.0",
            plugin_dir=tmp_path,
            author="Test Author",
            description="Test description",
            framework_version=">=2.0",
            entry_point="src/main.py",
            execution_mode=ExecutionMode.TRUSTED,
            requires=["other_plugin"],
            permissions=[{"resource": "db.*", "actions": ["read"]}],
            env={"KEY": "value"},
        )

        assert manifest.name == "test_plugin"
        assert manifest.version == "2.0.0"
        assert manifest.author == "Test Author"
        assert manifest.execution_mode == ExecutionMode.TRUSTED
        assert manifest.requires == ["other_plugin"]

    def test_from_raw(self, tmp_path):
        """Test creating manifest from raw dictionary."""
        raw = {
            "name": "test_plugin",
            "version": "1.0.0",
            "author": "Test",
            "description": "Test plugin",
            "entry_point": "src/main.py",
            "resources": {
                "timeout_seconds": 20,
                "max_memory_mb": 256,
            },
            "runtime": {
                "health_check": {
                    "enabled": True,
                    "interval_seconds": 60,
                }
            },
            "custom_config": {"option": "value"},
        }

        manifest = PluginManifest.from_raw(
            raw=raw,
            mode=ExecutionMode.TRUSTED,
            resolved_env={"KEY": "value"},
            requires=["dep1"],
            plugin_dir=tmp_path,
        )

        assert manifest.name == "test_plugin"
        assert manifest.resources.timeout_seconds == 20
        assert manifest.resources.max_memory_mb == 256
        assert manifest.runtime.health_check.interval_seconds == 60

    def test_repr(self, tmp_path):
        """Test string representation."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            plugin_dir=tmp_path,
            execution_mode=ExecutionMode.TRUSTED,
        )

        repr_str = repr(manifest)

        assert "test_plugin" in repr_str
        assert "1.0.0" in repr_str
        assert "trusted" in repr_str
