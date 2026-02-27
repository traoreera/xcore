"""
Tests for security components.
"""

import tempfile
from pathlib import Path

import pytest

from xcore.kernel.api.contract import ExecutionMode
from xcore.kernel.security.validation import (
    ASTScanner,
    ManifestError,
    ManifestValidator,
    ScanResult,
)


class TestManifestValidator:
    """Test ManifestValidator."""

    @pytest.fixture
    def validator(self):
        """Create ManifestValidator instance."""
        return ManifestValidator()

    @pytest.fixture
    def temp_plugin_dir(self):
        """Create temporary plugin directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    def test_load_valid_yaml_manifest(self, validator, temp_plugin_dir):
        """Test loading valid YAML manifest."""
        manifest_content = """
name: test_plugin
version: 1.0.0
author: Test
execution_mode: trusted
"""
        (temp_plugin_dir / "plugin.yaml").write_text(manifest_content)

        manifest = validator.load_and_validate(temp_plugin_dir)

        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.author == "Test"
        assert manifest.execution_mode == ExecutionMode.TRUSTED

    def test_load_valid_json_manifest(self, validator, temp_plugin_dir):
        """Test loading valid JSON manifest."""
        manifest_content = """{
            "name": "json_plugin",
            "version": "2.0.0",
            "execution_mode": "sandboxed"
        }"""
        (temp_plugin_dir / "plugin.json").write_text(manifest_content)

        manifest = validator.load_and_validate(temp_plugin_dir)

        assert manifest.name == "json_plugin"
        assert manifest.version == "2.0.0"
        assert manifest.execution_mode == ExecutionMode.SANDBOXED

    def test_load_missing_required_fields(self, validator, temp_plugin_dir):
        """Test loading manifest with missing required fields."""
        manifest_content = """
version: 1.0.0
"""
        (temp_plugin_dir / "plugin.yaml").write_text(manifest_content)

        with pytest.raises(ManifestError) as exc_info:
            validator.load_and_validate(temp_plugin_dir)

        assert "name" in str(exc_info.value)

    def test_load_invalid_execution_mode(self, validator, temp_plugin_dir):
        """Test loading manifest with invalid execution mode."""
        manifest_content = """
name: test_plugin
version: 1.0.0
execution_mode: invalid_mode
"""
        (temp_plugin_dir / "plugin.yaml").write_text(manifest_content)

        with pytest.raises(ManifestError) as exc_info:
            validator.load_and_validate(temp_plugin_dir)

        assert "execution_mode" in str(exc_info.value)

    def test_load_no_manifest_file(self, validator, temp_plugin_dir):
        """Test loading when no manifest file exists."""
        with pytest.raises(ManifestError) as exc_info:
            validator.load_and_validate(temp_plugin_dir)

        assert "Aucun manifeste" in str(exc_info.value)

    def test_invalid_requires_type(self, validator, temp_plugin_dir):
        """Test manifest with invalid requires type."""
        manifest_content = """
name: test_plugin
version: 1.0.0
requires: "not_a_list"
"""
        (temp_plugin_dir / "plugin.yaml").write_text(manifest_content)

        with pytest.raises(ManifestError) as exc_info:
            validator.load_and_validate(temp_plugin_dir)

        assert "requires" in str(exc_info.value)


class TestASTScanner:
    """Test AST Scanner for sandbox security."""

    @pytest.fixture
    def scanner(self):
        """Create ASTScanner instance."""
        return ASTScanner()

    @pytest.fixture
    def temp_plugin_dir(self):
        """Create temporary plugin directory with src."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / "src").mkdir()
            yield plugin_dir

    def test_scan_safe_code(self, scanner, temp_plugin_dir):
        """Test scanning safe plugin code."""
        safe_code = """
import json
import re
from typing import Dict

def process(data: dict) -> dict:
    return json.dumps(data)
"""
        (temp_plugin_dir / "src" / "main.py").write_text(safe_code)

        result = scanner.scan(temp_plugin_dir)

        assert result.passed is True
        assert len(result.errors) == 0

    def test_scan_forbidden_import(self, scanner, temp_plugin_dir):
        """Test scanning code with forbidden import."""
        bad_code = """
import os
import sys

def read_file():
    return os.listdir("/")
"""
        (temp_plugin_dir / "src" / "main.py").write_text(bad_code)

        result = scanner.scan(temp_plugin_dir)

        assert result.passed is False
        assert len(result.errors) > 0
        assert any("os" in err for err in result.errors)

    def test_scan_subprocess_import(self, scanner, temp_plugin_dir):
        """Test scanning code with subprocess import."""
        bad_code = """
import subprocess

def run_command(cmd):
    return subprocess.run(cmd, shell=True)
"""
        (temp_plugin_dir / "src" / "main.py").write_text(bad_code)

        result = scanner.scan(temp_plugin_dir)

        assert result.passed is False
        assert any("subprocess" in err for err in result.errors)

    def test_scan_eval_exec(self, scanner, temp_plugin_dir):
        """Test scanning code with eval/exec."""
        bad_code = """
def unsafe_eval(code):
    return eval(code)
"""
        (temp_plugin_dir / "src" / "main.py").write_text(bad_code)

        result = scanner.scan(temp_plugin_dir)

        assert result.passed is False
        assert any("eval" in err for err in result.errors)

    def test_scan_dunder_import(self, scanner, temp_plugin_dir):
        """Test scanning code with __import__."""
        bad_code = """
def dynamic_import(module):
    return __import__(module)
"""
        (temp_plugin_dir / "src" / "main.py").write_text(bad_code)

        result = scanner.scan(temp_plugin_dir)

        assert result.passed is False
        assert any("__import__" in err for err in result.errors)

    def test_scan_syntax_error(self, scanner, temp_plugin_dir):
        """Test scanning code with syntax error."""
        bad_code = """
def broken(
    missing closing parenthesis
"""
        (temp_plugin_dir / "src" / "main.py").write_text(bad_code)

        result = scanner.scan(temp_plugin_dir)

        assert result.passed is False
        assert len(result.errors) > 0

    def test_scan_no_src_dir(self, scanner):
        """Test scanning plugin without src directory."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)

            result = scanner.scan(plugin_dir)

            assert result.passed is False
            assert "src/" in str(result.errors)

    def test_scan_empty_src(self, scanner, temp_plugin_dir):
        """Test scanning empty src directory."""
        result = scanner.scan(temp_plugin_dir)

        assert result.passed is True
        assert len(result.warnings) > 0

    def test_scan_with_whitelist(self, scanner, temp_plugin_dir):
        """Test scanning with custom whitelist."""
        code = """
import custom_module

def process():
    return custom_module.do_something()
"""
        (temp_plugin_dir / "src" / "main.py").write_text(code)

        result = scanner.scan(temp_plugin_dir, whitelist=["custom_module"])

        # Should pass if custom_module is in whitelist
        assert result.passed is True


class TestScanResult:
    """Test ScanResult dataclass."""

    def test_initial_state(self):
        """Test initial scan result state."""
        result = ScanResult()

        assert result.passed is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self):
        """Test adding error."""
        result = ScanResult()

        result.add_error("Test error")

        assert result.passed is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test adding warning."""
        result = ScanResult()

        result.add_warning("Test warning")

        assert result.passed is True  # Warnings don't fail scan
        assert "Test warning" in result.warnings

    def test_str_representation(self):
        """Test string representation."""
        result = ScanResult()
        result.add_error("Error 1")
        result.add_warning("Warning 1")

        str_repr = str(result)

        assert "❌" in str_repr
        assert "⚠️" in str_repr
