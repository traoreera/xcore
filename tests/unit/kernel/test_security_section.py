"""Tests for kernel security section (_SimpleManifest, ScanResult, constants)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestScanResult:
    def test_default_passed(self):
        from xcore.kernel.security.section import ScanResult
        r = ScanResult()
        assert r.passed is True
        assert r.errors == []

    def test_add_error(self):
        from xcore.kernel.security.section import ScanResult
        r = ScanResult()
        r.add_error("bad import")
        assert r.passed is False
        assert "bad import" in r.errors

    def test_add_warning(self):
        from xcore.kernel.security.section import ScanResult
        r = ScanResult()
        r.add_warning("suspicious")
        assert r.passed is True
        assert "suspicious" in r.warnings

    def test_str_passed(self):
        from xcore.kernel.security.section import ScanResult
        r = ScanResult()
        s = str(r)
        assert "Scan" in s

    def test_str_failed(self):
        from xcore.kernel.security.section import ScanResult
        r = ScanResult()
        r.add_error("forbidden import: os")
        s = str(r)
        assert "forbidden import" in s


class TestSimpleManifest:
    def test_basic(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {"name": "test_plugin", "version": "1.0.0"}
        mode = MagicMock()
        m = _SimpleManifest(raw, mode, "dev", [], tmp_path)
        assert m.name == "test_plugin"
        assert m.version == "1.0.0"
        assert m.author == "unknown"
        assert m.description == ""

    def test_with_optional_fields(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {
            "name": "plugin",
            "version": "2.0",
            "author": "Alice",
            "description": "A test plugin",
            "framework_version": ">=2.0",
            "entry_point": "src/plugin.py",
            "allowed_imports": ["json", "re"],
        }
        m = _SimpleManifest(raw, MagicMock(), "prod", [], tmp_path)
        assert m.author == "Alice"
        assert m.description == "A test plugin"
        assert "json" in m.allowed_imports

    def test_resources_defaults(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {"name": "p", "version": "1.0"}
        m = _SimpleManifest(raw, MagicMock(), "dev", [], tmp_path)
        assert m.resources.timeout_seconds == 10
        assert m.resources.max_memory_mb == 128
        assert m.resources.rate_limit.calls == 100

    def test_runtime_defaults(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {"name": "p", "version": "1.0"}
        m = _SimpleManifest(raw, MagicMock(), "dev", [], tmp_path)
        assert m.runtime.health_check.enabled is True
        assert m.runtime.retry.max_attempts == 1

    def test_filesystem_defaults(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {"name": "p", "version": "1.0"}
        m = _SimpleManifest(raw, MagicMock(), "dev", [], tmp_path)
        assert "data/" in m.filesystem.allowed_paths

    def test_requires_string_converted(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {"name": "p", "version": "1.0"}
        m = _SimpleManifest(raw, MagicMock(), "dev", ["core"], tmp_path)
        # PluginDependency.from_raw("core") should not raise
        assert len(m.requires) == 1

    def test_extra_empty(self, tmp_path):
        from xcore.kernel.security.section import _SimpleManifest
        raw = {"name": "p", "version": "1.0"}
        m = _SimpleManifest(raw, MagicMock(), "dev", [], tmp_path)
        assert m.extra == {}


class TestConstants:
    def test_forbidden_builtins_contains_eval(self):
        from xcore.kernel.security.section import FORBIDDEN_BUILTINS
        assert "eval" in FORBIDDEN_BUILTINS
        assert "exec" in FORBIDDEN_BUILTINS

    def test_forbidden_attributes(self):
        from xcore.kernel.security.section import FORBIDDEN_ATTRIBUTES
        assert "__globals__" in FORBIDDEN_ATTRIBUTES

    def test_default_forbidden_contains_os(self):
        from xcore.kernel.security.section import DEFAULT_FORBIDDEN
        assert "os" in DEFAULT_FORBIDDEN

    def test_default_allowed_contains_json(self):
        from xcore.kernel.security.section import DEFAULT_ALLOWED
        assert "json" in DEFAULT_ALLOWED
