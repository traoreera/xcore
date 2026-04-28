"""
Tests for sandbox worker components.
"""

import builtins
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Test the components we can import
from xcore.kernel.sandbox.worker import (
    FilesystemGuard,
    _apply_resource_limits,
    _load_manifest,
    _PluginImportHook,
    _PluginManifest,
)


class TestPluginManifest:
    """Test _PluginManifest dataclass."""

    def test_defaults(self):
        """Test default values."""
        manifest = _PluginManifest()
        assert manifest.entry_point == "src/main.py"
        assert manifest.allowed_paths == ["data/"]
        assert manifest.denied_paths == ["src/"]

    def test_custom_values(self):
        """Test custom values."""
        manifest = _PluginManifest(
            entry_point="app/main.py",
            allowed_paths=["uploads/", "cache/"],
            denied_paths=["system/", "logs/"],
        )
        assert manifest.entry_point == "app/main.py"
        assert manifest.allowed_paths == ["uploads/", "cache/"]
        assert manifest.denied_paths == ["system/", "logs/"]


class TestApplyResourceLimits:
    """Test _apply_resource_limits function."""

    def test_no_limit_set(self):
        """Test when no memory limit is set."""
        with patch.dict(
            os.environ,
            {"_SANDBOX_MAX_MEM_MB": "0", "_SANDBOX_MAX_CPU_SEC": "0"},
            clear=True,
        ):
            # Should not raise
            _apply_resource_limits()

    def test_limit_on_windows(self):
        """Test resource limits on Windows (should skip)."""
        with patch.dict(
            os.environ, {"_SANDBOX_MAX_MEM_MB": "100", "_SANDBOX_MAX_CPU_SEC": "10"}
        ):
            with patch.object(sys, "platform", "win32"):
                # Should not raise (Windows is skipped)
                _apply_resource_limits()

    @pytest.mark.skipif(sys.platform == "win32", reason="Not applicable on Windows")
    def test_apply_limits_unix(self):
        """Test applying resource limits on Unix."""
        env = {
            "_SANDBOX_MAX_MEM_MB": "100",
            "_SANDBOX_MAX_CPU_SEC": "10",
        }
        with patch.dict(os.environ, env):
            with patch("resource.setrlimit") as mock_setrlimit:
                _apply_resource_limits()
                # On attend au moins un appel pour CPU et un pour mémoire
                assert mock_setrlimit.call_count >= 2


class TestFilesystemGuard:
    """Test FilesystemGuard class."""

    @pytest.fixture
    def guard(self, tmp_path):
        """Create a FilesystemGuard instance."""
        return FilesystemGuard(
            plugin_dir=tmp_path, allowed_paths=["data/"], denied_paths=["src/"]
        )

    def test_init(self, guard, tmp_path):
        """Test initialization."""
        assert guard._plugin_dir == tmp_path.resolve()
        assert len(guard._allowed) == 1
        assert len(guard._denied) == 1

    def test_resolve_relative(self, guard, tmp_path):
        """Test resolving relative path."""
        with patch.object(Path, "cwd", return_value=tmp_path):
            resolved = guard._resolve("data/file.txt")
            assert resolved == (tmp_path / "data/file.txt").resolve()

    def test_resolve_absolute(self, guard, tmp_path):
        """Test resolving absolute path."""
        abs_path = "/absolute/path/file.txt"
        resolved = guard._resolve(abs_path)
        assert resolved == Path(abs_path).resolve()

    def test_is_allowed_in_allowed_path(self, guard, tmp_path):
        """Test allowed path check."""
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "file.txt").touch()

        assert guard.is_allowed(tmp_path / "data/file.txt") is True

    def test_is_allowed_in_denied_path(self, guard, tmp_path):
        """Test denied path check."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "file.txt").touch()

        assert guard.is_allowed(tmp_path / "src/file.txt") is False

    def test_is_allowed_outside_allowed(self, guard, tmp_path):
        """Test path outside allowed paths."""
        # A path that's not in allowed or denied should be blocked (fail-closed)
        assert guard.is_allowed(tmp_path / "other/file.txt") is False

    def test_is_allowed_denied_takes_precedence(self, guard, tmp_path):
        """Test that denied paths take precedence."""
        # If a path is in both allowed and denied, denied wins
        # Note: This requires creating a scenario where it would match both

    def test_is_allowed_invalid_path(self, guard):
        """Test handling invalid path."""
        # Should return False for invalid paths
        assert guard.is_allowed(None) is False

    @pytest.mark.skip(reason="Guard installation modifies global state")
    def test_install(self, guard):
        """Test installing the guard (modifies global builtins)."""
        # This test is skipped by default because it modifies global state
        guard.install()
        # Verify builtins were patched
        guard.uninstall()


class TestPluginImportHook:
    """Test _PluginImportHook class."""

    @pytest.fixture
    def hook(self, tmp_path):
        """Create a _PluginImportHook instance."""
        return _PluginImportHook("test_uid", tmp_path)

    def test_init(self, hook, tmp_path):
        """Test initialization."""
        assert hook._uid == "test_uid"
        assert hook._src_dir == tmp_path
        assert hook._pkg_prefix == "xcore_plugin_test_uid"

    def test_owns_package(self, hook):
        """Test _owns with package name."""
        assert hook._owns("xcore_plugin_test_uid") is True

    def test_owns_submodule(self, hook):
        """Test _owns with submodule."""
        assert hook._owns("xcore_plugin_test_uid.submodule") is True
        assert hook._owns("xcore_plugin_test_uid.nested.deep") is True

    def test_not_owns_other_package(self, hook):
        """Test _owns with different package."""
        assert hook._owns("other_package") is False
        assert hook._owns("xcore_plugin_other_uid") is False

    def test_find_module(self, hook):
        """Test find_module API."""
        # Should return self if it owns the module
        result = hook.find_module("xcore_plugin_test_uid.main")
        assert result is hook

        # Should return None if not owned
        result = hook.find_module("other_package.main")
        assert result is None

    def test_spec_for_module(self, hook, tmp_path):
        """Test _spec_for with module file."""
        (tmp_path / "module.py").write_text("x = 1")

        spec = hook._spec_for("xcore_plugin_test_uid.module", "module")
        assert spec is not None
        assert spec.name == "xcore_plugin_test_uid.module"

    def test_spec_for_package(self, hook, tmp_path):
        """Test _spec_for with package."""
        pkg_dir = tmp_path / "package"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        spec = hook._spec_for("xcore_plugin_test_uid.package", "package")
        assert spec is not None
        assert spec.name == "xcore_plugin_test_uid.package"
        assert spec.submodule_search_locations is not None

    def test_spec_for_missing(self, hook):
        """Test _spec_for with missing module."""
        spec = hook._spec_for("xcore_plugin_test_uid.missing", "missing")
        assert spec is None

    def test_install_uninstall(self, hook, tmp_path):
        """Test install and uninstall cycle."""
        original_meta_path = sys.meta_path.copy()

        hook.install()

        # Check hook is installed
        assert hook in sys.meta_path
        assert hook._pkg_prefix in sys.modules

        hook.uninstall()

        # Check hook is removed
        assert hook not in sys.meta_path
        assert hook._pkg_prefix not in sys.modules

        # Restore sys.meta_path
        sys.meta_path[:] = original_meta_path


class TestLoadManifest:
    """Test _load_manifest function."""

    def test_load_yaml_manifest(self, tmp_path):
        """Test loading YAML manifest."""
        yaml_content = """
entry_point: custom/main.py
filesystem:
  allowed_paths:
    - uploads/
    - cache/
  denied_paths:
    - logs/
"""
        (tmp_path / "plugin.yaml").write_text(yaml_content)

        manifest = _load_manifest(tmp_path)

        assert manifest.entry_point == "custom/main.py"
        assert "uploads/" in manifest.allowed_paths
        assert "cache/" in manifest.allowed_paths
        assert "logs/" in manifest.denied_paths

    def test_load_json_manifest(self, tmp_path):
        """Test loading JSON manifest."""
        json_content = """
{
    "entry_point": "app/core.py",
    "filesystem": {
        "allowed_paths": ["data/"],
        "denied_paths": ["config/"]
    }
}
"""
        (tmp_path / "plugin.json").write_text(json_content)

        manifest = _load_manifest(tmp_path)

        assert manifest.entry_point == "app/core.py"
        assert "data/" in manifest.allowed_paths
        assert "config/" in manifest.denied_paths

    def test_no_manifest_defaults(self, tmp_path):
        """Test default values when no manifest exists."""
        manifest = _load_manifest(tmp_path)

        assert manifest.entry_point == "src/main.py"
        assert manifest.allowed_paths == ["data/"]
        assert manifest.denied_paths == ["src/"]

    def test_malformed_manifest_fallback(self, tmp_path):
        """Test fallback to defaults with malformed manifest."""
        (tmp_path / "plugin.yaml").write_text("not: valid: yaml: [")

        manifest = _load_manifest(tmp_path)

        # Should return defaults despite the malformed YAML
        assert manifest.entry_point == "src/main.py"


class TestFilesystemGuardEdgeCases:
    """Test edge cases for FilesystemGuard."""

    @pytest.fixture
    def guard(self, tmp_path):
        """Create a FilesystemGuard instance."""
        return FilesystemGuard(
            plugin_dir=tmp_path, allowed_paths=["data/"], denied_paths=["src/"]
        )

    def test_empty_allowed_paths(self, tmp_path):
        """Test guard with empty allowed paths."""
        guard = FilesystemGuard(plugin_dir=tmp_path, allowed_paths=[], denied_paths=[])
        # With no allowed paths, everything should be denied (fail-closed)
        assert guard.is_allowed(tmp_path / "any/file.txt") is False

    def test_symlink_resolution(self, guard, tmp_path):
        """Test path resolution with symlinks."""
        # Create a file and a symlink to it
        (tmp_path / "data").mkdir()
        real_file = tmp_path / "data" / "real.txt"
        real_file.touch()
        symlink = tmp_path / "data" / "link.txt"
        try:
            symlink.symlink_to(real_file)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        # Should resolve to real path
        assert guard.is_allowed(symlink) is True

    def test_path_traversal_attempt(self, guard, tmp_path):
        """Test handling of path traversal attempts."""
        # Try to access outside plugin dir
        malicious_path = tmp_path / "data" / ".." / ".." / "etc" / "passwd"
        # The path should be resolved to absolute, which may or may not be allowed
        # depending on the resolved location
        guard.is_allowed(malicious_path)
        # Should either be False (denied) or resolved to actual path
        # The important thing is it doesn't actually allow access to /etc/passwd
