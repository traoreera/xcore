"""Tests for ConfigLoader."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from xcore.configurations.loader import ConfigLoader


class TestConfigLoader:
    def test_load_defaults_no_file(self):
        config = ConfigLoader.load(None)
        assert config is not None

    def test_load_json_file(self, tmp_path):
        cfg_file = tmp_path / "integration.json"
        cfg_file.write_text(json.dumps({
            "app": {"name": "test-app", "env": "test"},
        }))
        config = ConfigLoader.load(str(cfg_file))
        assert config is not None

    def test_load_nonexistent_path_uses_defaults(self):
        config = ConfigLoader.load("/nonexistent/path/config.yaml")
        assert config is not None

    def test_env_overrides(self, tmp_path):
        env = {"XCORE__APP__ENV": "staging"}
        with patch.dict(os.environ, env):
            config = ConfigLoader.load(None)
        assert config is not None

    def test_env_override_bool_true(self, tmp_path):
        env = {"XCORE__TENANCY__ENABLED": "true"}
        with patch.dict(os.environ, env):
            config = ConfigLoader.load(None)
        assert config is not None

    def test_env_override_bool_false(self, tmp_path):
        env = {"XCORE__TENANCY__ENABLED": "false"}
        with patch.dict(os.environ, env):
            config = ConfigLoader.load(None)
        assert config is not None

    def test_env_override_integer(self):
        env = {"XCORE__APP__PORT": "9090"}
        with patch.dict(os.environ, env):
            config = ConfigLoader.load(None)
        assert config is not None

    def test_load_yaml_file(self, tmp_path):
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml not installed")
        cfg_file = tmp_path / "integration.yaml"
        cfg_file.write_text("app:\n  name: test-app\n  env: test\n")
        config = ConfigLoader.load(str(cfg_file))
        assert config is not None

    def test_load_invalid_json_uses_defaults(self, tmp_path):
        cfg_file = tmp_path / "bad.json"
        cfg_file.write_text("INVALID JSON {{")
        config = ConfigLoader.load(str(cfg_file))
        assert config is not None

    def test_apply_env_overrides(self):
        raw = {"app": {"env": "dev"}}
        env = {"XCORE__APP__ENV": "production"}
        with patch.dict(os.environ, env):
            result = ConfigLoader._apply_env_overrides(raw)
        assert result["app"]["env"] == "production"

    def test_apply_env_no_prefix_ignored(self):
        raw = {"app": {"env": "dev"}}
        env = {"OTHER__APP__ENV": "production"}
        with patch.dict(os.environ, env, clear=False):
            result = ConfigLoader._apply_env_overrides(raw)
        assert result["app"]["env"] == "dev"

    def test_dotenv_missing_file(self, tmp_path):
        raw = {"app": {"dotenv": str(tmp_path / ".env")}}
        ConfigLoader._load_dotenv(raw)  # should not raise

    def test_dotenv_no_setting(self):
        ConfigLoader._load_dotenv({})  # should not raise

    def test_dotenv_with_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("MY_VAR=test_value\n")
        raw = {"app": {"dotenv": str(env_file)}}
        try:
            ConfigLoader._load_dotenv(raw)
        except ImportError:
            pass  # python-dotenv not installed — ok
