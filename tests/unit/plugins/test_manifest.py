"""
Tests for PluginManifest and related dataclasses.
"""

import pytest

from xcore.kernel.api.contract import ExecutionMode
from xcore.sdk.plugin_base import (
    FilesystemConfig,
    HealthCheckConfig,
    PluginDependency,
    PluginManifest,
    RateLimitConfig,
    ResourceConfig,
    RetryConfig,
    RuntimeConfig,
    VersionConstraint,
)


class TestVersionConstraint:
    """Test VersionConstraint class."""

    def test_exact_match(self):
        """Test exact version matching."""
        vc = VersionConstraint("1.2.3")
        assert vc.matches("1.2.3") is True
        assert vc.matches("1.2.4") is False

    def test_greater_than_equal(self):
        """Test >= operator."""
        vc = VersionConstraint(">=1.2.0")
        assert vc.matches("1.2.0") is True
        assert vc.matches("1.3.0") is True
        assert vc.matches("2.0.0") is True
        assert vc.matches("1.1.9") is False

    def test_less_than_equal(self):
        """Test <= operator."""
        vc = VersionConstraint("<=1.2.0")
        assert vc.matches("1.2.0") is True
        assert vc.matches("1.1.9") is True
        assert vc.matches("1.3.0") is False

    def test_greater_than(self):
        """Test > operator."""
        vc = VersionConstraint(">1.2.0")
        assert vc.matches("1.2.1") is True
        assert vc.matches("1.2.0") is False
        assert vc.matches("1.1.9") is False

    def test_less_than(self):
        """Test < operator."""
        vc = VersionConstraint("<1.2.0")
        assert vc.matches("1.1.9") is True
        assert vc.matches("1.2.0") is False
        assert vc.matches("1.3.0") is False

    def test_not_equal(self):
        """Test != operator."""
        vc = VersionConstraint("!=1.2.0")
        assert vc.matches("1.2.1") is True
        assert vc.matches("1.2.0") is False

    def test_caret_semver(self):
        """Test ^ (caret) semver operator."""
        vc = VersionConstraint("^1.2.3")
        assert vc.matches("1.2.3") is True
        assert vc.matches("1.3.0") is True
        assert vc.matches("1.9.9") is True
        assert vc.matches("2.0.0") is False
        assert vc.matches("1.2.2") is False

    def test_tilde_semver(self):
        """Test ~ (tilde) semver operator."""
        vc = VersionConstraint("~1.2.3")
        assert vc.matches("1.2.3") is True
        assert vc.matches("1.2.9") is True
        assert vc.matches("1.3.0") is False
        assert vc.matches("1.2.2") is False

    def test_combined_operators(self):
        """Test multiple operators."""
        vc = VersionConstraint(">=1.0.0,<2.0.0")
        assert vc.matches("1.0.0") is True
        assert vc.matches("1.5.0") is True
        assert vc.matches("1.9.9") is True
        assert vc.matches("2.0.0") is False
        assert vc.matches("0.9.9") is False

    def test_version_with_v_prefix(self):
        """Test version with v/V prefix."""
        vc = VersionConstraint(">=1.0.0")
        assert vc.matches("v1.0.0") is True
        assert vc.matches("V1.5.0") is True


class TestPluginDependency:
    """Test PluginDependency class."""

    def test_default_wildcard_constraint(self):
        """Test default wildcard constraint."""
        dep = PluginDependency(name="test_plugin")
        assert dep.version_constraint == "*"
        assert dep.is_compatible("1.0.0") is True
        assert dep.is_compatible("any.version") is True

    def test_specific_constraint(self):
        """Test specific constraint."""
        dep = PluginDependency(name="test_plugin", version_constraint=">=2.0.0")
        assert dep.is_compatible("2.0.0") is True
        assert dep.is_compatible("3.0.0") is True
        assert dep.is_compatible("1.9.9") is False

    def test_from_raw_string(self):
        """Test from_raw with string."""
        dep = PluginDependency.from_raw("other_plugin")
        assert dep.name == "other_plugin"
        assert dep.version_constraint == "*"

    def test_from_raw_dict(self):
        """Test from_raw with dict."""
        dep = PluginDependency.from_raw({"name": "other_plugin", "version": ">=2.0.0"})
        assert dep.name == "other_plugin"
        assert dep.version_constraint == ">=2.0.0"

    def test_from_raw_dict_no_name(self):
        """Test from_raw with dict missing name."""
        with pytest.raises(ValueError, match="requires a 'name' field"):
            PluginDependency.from_raw({"version": ">=2.0.0"})

    def test_from_raw_invalid_type(self):
        """Test from_raw with invalid type."""
        with pytest.raises(TypeError):
            PluginDependency.from_raw(123)

    def test_equality(self):
        """Test equality comparison."""
        dep1 = PluginDependency(name="plugin_a")
        dep2 = PluginDependency(name="plugin_a", version_constraint=">=1.0")
        dep3 = PluginDependency(name="plugin_b")

        assert dep1 == dep2
        assert dep1 != dep3
        assert dep1 == "plugin_a"
        assert dep1 != "plugin_b"

    def test_hash(self):
        """Test hash function."""
        dep1 = PluginDependency(name="plugin_a")
        dep2 = PluginDependency(name="plugin_a")
        dep3 = PluginDependency(name="plugin_b")

        assert hash(dep1) == hash(dep2)
        assert hash(dep1) != hash(dep3)


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = RateLimitConfig()
        assert config.calls == 100
        assert config.period_seconds == 60

    def test_custom_values(self):
        """Test custom values."""
        config = RateLimitConfig(calls=50, period_seconds=30)
        assert config.calls == 50
        assert config.period_seconds == 30


class TestResourceConfig:
    """Test ResourceConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = ResourceConfig()
        assert config.timeout_seconds == 10
        assert config.max_memory_mb == 128
        assert config.max_disk_mb == 50
        assert isinstance(config.rate_limit, RateLimitConfig)

    def test_custom_values(self):
        """Test custom values."""
        rl = RateLimitConfig(calls=200, period_seconds=120)
        config = ResourceConfig(
            timeout_seconds=20, max_memory_mb=256, max_disk_mb=100, rate_limit=rl
        )
        assert config.timeout_seconds == 20
        assert config.max_memory_mb == 256
        assert config.max_disk_mb == 100
        assert config.rate_limit.calls == 200


class TestHealthCheckConfig:
    """Test HealthCheckConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = HealthCheckConfig()
        assert config.enabled is True
        assert config.interval_seconds == 30
        assert config.timeout_seconds == 3


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = RetryConfig()
        assert config.max_attempts == 1
        assert config.backoff_seconds == 0.0


class TestRuntimeConfig:
    """Test RuntimeConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = RuntimeConfig()
        assert isinstance(config.health_check, HealthCheckConfig)
        assert isinstance(config.retry, RetryConfig)


class TestFilesystemConfig:
    """Test FilesystemConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = FilesystemConfig()
        assert config.allowed_paths == ["data/"]
        assert config.denied_paths == ["src/"]

    def test_custom_values(self):
        """Test custom values."""
        config = FilesystemConfig(
            allowed_paths=["data/", "uploads/"], denied_paths=["system/", "config/"]
        )
        assert config.allowed_paths == ["data/", "uploads/"]
        assert config.denied_paths == ["system/", "config/"]


class TestPluginManifest:
    """Test PluginManifest dataclass."""

    def test_basic_creation(self, tmp_path):
        """Test basic manifest creation."""
        manifest = PluginManifest(
            name="test_plugin", version="1.0.0", plugin_dir=tmp_path
        )

        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.plugin_dir == tmp_path
        assert manifest.author == "unknown"
        assert manifest.description == ""
        assert manifest.framework_version == ">=2.0"
        assert manifest.entry_point == "src/main.py"
        assert manifest.execution_mode == ExecutionMode.LEGACY

    def test_repr(self, tmp_path):
        """Test __repr__ method."""
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

    def test_from_raw_basic(self, tmp_path):
        """Test from_raw with minimal data."""
        raw = {"name": "my_plugin", "version": "1.0.0"}

        manifest = PluginManifest.from_raw(
            raw=raw,
            mode=ExecutionMode.TRUSTED,
            resolved_env={},
            requires=[],
            plugin_dir=tmp_path,
        )

        assert manifest.name == "my_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.execution_mode == ExecutionMode.TRUSTED

    def test_from_raw_full(self, tmp_path):
        """Test from_raw with full data."""
        raw = {
            "name": "my_plugin",
            "version": "2.0.0",
            "author": "Test Author",
            "description": "Test description",
            "framework_version": ">=2.0",
            "entry_point": "custom/main.py",
            "requires": ["other_plugin"],
            "allowed_imports": ["requests", "json"],
            "permissions": [{"resource": "db.*", "actions": ["read"]}],
            "resources": {
                "timeout_seconds": 30,
                "max_memory_mb": 256,
                "max_disk_mb": 100,
                "rate_limit": {"calls": 200, "period_seconds": 120},
            },
            "runtime": {
                "health_check": {"enabled": False, "interval_seconds": 60},
                "retry": {"max_attempts": 3, "backoff_seconds": 1.0},
            },
            "filesystem": {
                "allowed_paths": ["data/", "uploads/"],
                "denied_paths": ["system/"],
            },
            "custom_key": "custom_value",
        }

        deps = [PluginDependency.from_raw("other_plugin")]

        manifest = PluginManifest.from_raw(
            raw=raw,
            mode=ExecutionMode.SANDBOXED,
            resolved_env={"KEY": "value"},
            requires=deps,
            plugin_dir=tmp_path,
        )

        assert manifest.name == "my_plugin"
        assert manifest.version == "2.0.0"
        assert manifest.author == "Test Author"
        assert manifest.description == "Test description"
        assert manifest.entry_point == "custom/main.py"
        assert manifest.execution_mode == ExecutionMode.SANDBOXED
        assert manifest.allowed_imports == ["requests", "json"]
        assert manifest.resources.timeout_seconds == 30
        assert manifest.resources.max_memory_mb == 256
        assert manifest.resources.rate_limit.calls == 200
        assert manifest.runtime.health_check.enabled is False
        assert manifest.runtime.retry.max_attempts == 3
        assert manifest.filesystem.allowed_paths == ["data/", "uploads/"]
        assert manifest.extra == {"custom_key": "custom_value"}

    def test_from_raw_with_dependencies(self, tmp_path):
        """Test from_raw with dependencies."""
        raw = {
            "name": "my_plugin",
            "version": "1.0.0",
            "requires": ["simple_dep", {"name": "versioned_dep", "version": ">=2.0.0"}],
        }

        deps = [
            PluginDependency.from_raw("simple_dep"),
            PluginDependency.from_raw({"name": "versioned_dep", "version": ">=2.0.0"}),
        ]

        manifest = PluginManifest.from_raw(
            raw=raw,
            mode=ExecutionMode.TRUSTED,
            resolved_env={},
            requires=deps,
            plugin_dir=tmp_path,
        )

        assert len(manifest.requires) == 2
        assert manifest.requires[0].name == "simple_dep"
        assert manifest.requires[1].name == "versioned_dep"
