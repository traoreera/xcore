"""
Tests for configuration loading and validation.
"""

import os

import pytest
import yaml

from xcore.configurations.loader import ConfigLoader
from xcore.configurations.sections import AppConfig, PluginConfig, ServicesConfig


class TestConfigLoader:
    """Test configuration loading."""

    def test_load_minimal_config(self, temp_dir):
        """Test loading minimal configuration."""
        config_path = temp_dir / "test.yaml"
        config_content = """
app:
  name: test-app
  secret_key: test-secret-key-for-testing

plugins:
  directory: ./plugins

services:
  databases: {}
  cache:
    backend: memory
"""
        config_path.write_text(config_content)

        config = ConfigLoader.load(str(config_path))

        assert config.app.name == "test-app"
        assert config.plugins.directory == "./plugins"
        assert config.services.cache.backend == "memory"

    def test_load_with_env_substitution(self, temp_dir):
        """Test environment variable substitution."""
        os.environ["TEST_SECRET"] = "from_environment"

        config_path = temp_dir / "test.yaml"
        config_content = """
app:
  name: test-app
  secret_key: ${TEST_SECRET}

plugins:
  directory: ./plugins

services:
  databases: {}
  cache:
    backend: memory
"""
        config_path.write_text(config_content)

        config = ConfigLoader.load(str(config_path))

        assert config.app.secret_key == "from_environment"

        del os.environ["TEST_SECRET"]

    def test_load_missing_file(self):
        """Test loading non-existent file."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load("/nonexistent/path.yaml")

    def test_load_invalid_yaml(self, temp_dir):
        """Test loading invalid YAML."""
        config_path = temp_dir / "test.yaml"
        config_path.write_text("invalid: yaml: : : content")

        with pytest.raises(Exception):
            ConfigLoader.load(str(config_path))


class TestAppConfig:
    """Test AppConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AppConfig(name="test", secret_key="secret")

        assert config.env == "production"
        assert config.debug is False
        assert config.plugin_prefix == "/plugin"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AppConfig(
            name="test",
            env="development",
            debug=True,
            secret_key="secret",
            plugin_prefix="/api/plugins",
            plugin_tags=["api", "v1"],
        )

        assert config.env == "development"
        assert config.debug is True
        assert config.plugin_prefix == "/api/plugins"


class TestPluginConfig:
    """Test PluginConfig dataclass."""

    def test_default_values(self):
        """Test default plugin configuration."""
        config = PluginConfig(directory="./plugins", secret_key=None)

        assert config.strict_trusted is False
        assert config.interval == 0
        assert config.entry_point == "src/main.py"

    def test_custom_values(self):
        """Test custom plugin configuration."""
        config = PluginConfig(
            directory="./custom_plugins",
            secret_key="signing_key",
            strict_trusted=True,
            interval=5,
        )

        assert config.strict_trusted is True
        assert config.interval == 5


class TestServicesConfig:
    """Test ServicesConfig dataclass."""

    def test_empty_config(self):
        """Test empty services configuration."""
        config = ServicesConfig(
            databases={}, cache=None, scheduler=None, extensions=None
        )

        assert config.databases == {}
        assert config.cache is None

    def test_database_config(self):
        """Test database configuration."""
        db_config = {
            "default": {
                "type": "postgresql",
                "url": "postgresql://localhost/db",
                "pool_size": 20,
            }
        }

        config = ServicesConfig(
            databases=db_config, cache=None, scheduler=None, extensions=None
        )

        assert "default" in config.databases
        assert config.databases["default"]["type"] == "postgresql"
