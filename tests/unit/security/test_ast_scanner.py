"""
Tests for ASTScanner and security validation.
"""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from xcore.kernel.security.validation import (
    DEFAULT_ALLOWED,
    DEFAULT_FORBIDDEN,
    ASTScanner,
    ManifestError,
    ManifestValidator,
    ScanResult,
    _SecurityVisitor,
    _resolve_env,
)


class TestScanResult:
    """Test ScanResult dataclass."""

    def test_default_state(self):
        """Test default ScanResult state."""
        result = ScanResult()
        assert result.passed is True
        assert result.errors == []
        assert result.warnings == []
        assert result.scanned == []

    def test_add_error(self):
        """Test add_error method."""
        result = ScanResult()
        result.add_error("Test error")

        assert result.passed is False
        assert result.errors == ["Test error"]

    def test_add_warning(self):
        """Test add_warning method."""
        result = ScanResult()
        result.add_warning("Test warning")

        assert result.passed is True  # Warnings don't fail the scan
        assert result.warnings == ["Test warning"]

    def test_str_passed(self):
        """Test __str__ when passed."""
        result = ScanResult(passed=True, errors=[], warnings=[])
        assert "✅" in str(result)

    def test_str_failed(self):
        """Test __str__ when failed."""
        result = ScanResult(passed=False, errors=["Error 1"], warnings=["Warning 1"])
        result_str = str(result)
        assert "❌" in result_str
        assert "Error 1" in result_str
        assert "Warning 1" in result_str


class TestImportVisitor:
    """Test _ImportVisitor AST visitor."""

    @pytest.fixture
    def visitor(self):
        """Create a visitor for testing."""
        return _SecurityVisitor(
            forbidden={"os", "sys"},
            allowed={"json", "re"},
            filename="test.py",
            path=Path("/test/test.py"),
        )

    def test_check_forbidden_import(self, visitor):
        """Test detecting forbidden import."""
        visitor._check("os", 10)
        assert len(visitor.errors) == 1
        assert "os" in visitor.errors[0]
        assert "10" in visitor.errors[0]

    def test_check_allowed_import(self, visitor):
        """Test allowed import doesn't add error."""
        visitor._check("json", 10)
        assert len(visitor.errors) == 0
        assert len(visitor.warnings) == 0

    def test_check_unknown_import(self, visitor):
        """Test unknown import adds warning."""
        visitor._check("unknown_module", 10)
        assert len(visitor.warnings) == 1
        assert "unknown_module" in visitor.warnings[0]

    def test_visit_import_forbidden(self, visitor):
        """Test visiting Import node with forbidden module."""
        code = "import os"
        tree = ast.parse(code)
        visitor.visit(tree)
        assert len(visitor.errors) == 1
        assert "os" in visitor.errors[0]

    def test_visit_import_allowed(self, visitor):
        """Test visiting Import node with allowed module."""
        code = "import json"
        tree = ast.parse(code)
        visitor.visit(tree)
        assert len(visitor.errors) == 0
        assert len(visitor.warnings) == 0

    def test_visit_import_from_forbidden(self, visitor):
        """Test visiting ImportFrom node with forbidden module."""
        code = "from os import path"
        tree = ast.parse(code)
        visitor.visit(tree)
        assert len(visitor.errors) == 1
        assert "os" in visitor.errors[0]

    def test_visit_import_submodule(self, visitor):
        """Test that submodule import checks root module."""
        code = "from os.path import join"
        tree = ast.parse(code)
        visitor.visit(tree)
        assert len(visitor.errors) == 1
        assert "os.path" in visitor.errors[0]

    def test_visit_call_dunder_import(self, visitor):
        """Test detecting __import__() call."""
        code = "module = __import__('os')"
        tree = ast.parse(code)
        visitor.visit(tree)
        assert len(visitor.errors) == 1
        assert "__import__" in visitor.errors[0]


class TestASTScanner:
    """Test ASTScanner class."""

    def test_default_lists(self):
        """Test default forbidden and allowed lists."""
        scanner = ASTScanner()

        # Check some expected defaults
        assert "os" in scanner.forbidden
        assert "subprocess" in scanner.forbidden
        assert "socket" in scanner.forbidden
        assert "json" in scanner.allowed
        assert "re" in scanner.allowed
        assert "xcore" in scanner.allowed

    def test_extra_forbidden(self):
        """Test adding extra forbidden modules."""
        scanner = ASTScanner(extra_forbidden={"custom_forbidden"})
        assert "custom_forbidden" in scanner.forbidden
        assert "os" in scanner.forbidden  # Still has defaults

    def test_extra_allowed(self):
        """Test adding extra allowed modules."""
        scanner = ASTScanner(extra_allowed={"custom_allowed"})
        assert "custom_allowed" in scanner.allowed
        assert "json" in scanner.allowed  # Still has defaults

    def test_scan_no_src_dir(self, tmp_path):
        """Test scan when src/ directory doesn't exist."""
        scanner = ASTScanner()
        result = scanner.scan(tmp_path)

        assert result.passed is False
        assert any("introuvable" in e for e in result.errors)

    def test_scan_empty_src(self, tmp_path):
        """Test scan with empty src/ directory."""
        (tmp_path / "src").mkdir()
        scanner = ASTScanner()
        result = scanner.scan(tmp_path)

        assert result.passed is True
        assert any("Aucun fichier" in w for w in result.warnings)

    def test_scan_valid_code(self, tmp_path):
        """Test scan with valid Python code."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("import json\nprint('hello')")

        scanner = ASTScanner()
        result = scanner.scan(tmp_path)

        assert result.passed is True
        assert "src/main.py" in result.scanned

    def test_scan_forbidden_import(self, tmp_path):
        """Test scan detects forbidden import."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "bad.py").write_text("import os\nimport subprocess")

        scanner = ASTScanner()
        result = scanner.scan(tmp_path)

        assert result.passed is False
        assert any("os" in e for e in result.errors)
        assert any("subprocess" in e for e in result.errors)

    def test_scan_with_whitelist(self, tmp_path):
        """Test scan respects whitelist."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("import custom_module")

        scanner = ASTScanner()
        result = scanner.scan(tmp_path, whitelist=["custom_module"])

        assert result.passed is True
        # Should be warning, not error, since it's whitelisted as allowed
        # But custom_module isn't in the allowed set by default, so it should
        # actually be a warning, not an error

    def test_scan_syntax_error(self, tmp_path):
        """Test scan handles syntax errors."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "broken.py").write_text("def broken(\n  pass")

        scanner = ASTScanner()
        result = scanner.scan(tmp_path)

        assert result.passed is False
        assert any("syntaxe" in e for e in result.errors)

    def test_scan_file_read_error(self, tmp_path):
        """Test scan handles file read errors."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        bad_file = src_dir / "unreadable.py"
        bad_file.write_text("content")

        scanner = ASTScanner()

        # Mock file read to raise exception
        with patch.object(Path, "read_text", side_effect=IOError("Permission denied")):
            # We need to patch the specific path's read_text
            with patch.object(
                bad_file, "read_text", side_effect=IOError("Permission denied")
            ):
                result = scanner.scan(tmp_path)

        assert result.passed is False


class TestResolveEnv:
    """Test _resolve_env function."""

    def test_no_env_var(self):
        """Test string without env var is returned as-is."""
        assert _resolve_env("plain_string") == "plain_string"

    def test_resolve_existing_env(self, monkeypatch):
        """Test resolving existing env var."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        assert _resolve_env("${TEST_VAR}") == "test_value"

    def test_resolve_missing_env(self):
        """Test resolving missing env var raises error."""
        with pytest.raises(ManifestError) as exc_info:
            _resolve_env("${MISSING_VAR}")

        assert "MISSING_VAR" in str(exc_info.value)
        assert "absente" in str(exc_info.value)


class TestManifestValidator:
    """Test ManifestValidator class."""

    @pytest.fixture
    def validator(self):
        return ManifestValidator()

    @pytest.fixture
    def valid_manifest(self, tmp_path):
        """Create a valid plugin.yaml file."""
        yaml_content = """
name: test_plugin
version: 1.0.0
execution_mode: trusted
author: Test Author
description: Test description
"""
        (tmp_path / "plugin.yaml").write_text(yaml_content)
        return tmp_path

    def test_read_raw_yaml(self, validator, tmp_path):
        """Test _read_raw with YAML file."""
        (tmp_path / "plugin.yaml").write_text("key: value\nlist:\n  - item1\n  - item2")

        result = validator._read_raw(tmp_path)
        assert result["key"] == "value"
        assert result["list"] == ["item1", "item2"]

    def test_read_raw_json(self, validator, tmp_path):
        """Test _read_raw with JSON file."""
        (tmp_path / "plugin.json").write_text('{"key": "value", "num": 42}')

        result = validator._read_raw(tmp_path)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_read_raw_no_manifest(self, validator, tmp_path):
        """Test _read_raw raises error when no manifest found."""
        with pytest.raises(ManifestError) as exc_info:
            validator._read_raw(tmp_path)

        assert "Aucun manifeste" in str(exc_info.value)

    def test_load_and_validate_missing_name(self, validator, tmp_path):
        """Test load_and_validate with missing name field."""
        (tmp_path / "plugin.yaml").write_text("version: 1.0.0")

        with pytest.raises(ManifestError) as exc_info:
            validator.load_and_validate(tmp_path)

        assert "name" in str(exc_info.value)

    def test_load_and_validate_missing_version(self, validator, tmp_path):
        """Test load_and_validate with missing version field."""
        (tmp_path / "plugin.yaml").write_text("name: test_plugin")

        with pytest.raises(ManifestError) as exc_info:
            validator.load_and_validate(tmp_path)

        assert "version" in str(exc_info.value)

    def test_inject_dotenv_disabled(self, validator, tmp_path):
        """Test _inject_dotenv when disabled."""
        # Should not raise
        validator._inject_dotenv(None, tmp_path)
        validator._inject_dotenv({"inject": False}, tmp_path)

    def test_inject_dotenv_missing_file(self, validator, tmp_path):
        """Test _inject_dotenv with missing file."""
        with pytest.raises(ManifestError) as exc_info:
            validator._inject_dotenv({"inject": True, "env_file": ".env"}, tmp_path)

        assert "introuvable" in str(exc_info.value)

    def test_inject_dotenv_path_traversal(self, validator, tmp_path):
        """Test _inject_dotenv blocks path traversal."""
        with pytest.raises(ManifestError) as exc_info:
            validator._inject_dotenv({"inject": True, "env_file": "../.env"}, tmp_path)

        assert "traversal" in str(exc_info.value)

    def test_yaml_import_error(self, validator, tmp_path):
        """Test _yaml raises error when pyyaml not installed."""
        with patch.dict("sys.modules", {"yaml": None}):
            (tmp_path / "test.yaml").touch()
            with pytest.raises(ManifestError) as exc_info:
                ManifestValidator._yaml(tmp_path / "test.yaml")

            assert "pyyaml" in str(exc_info.value)


class TestDefaultLists:
    """Test DEFAULT_FORBIDDEN and DEFAULT_ALLOWED constants."""

    def test_forbidden_contains_dangerous(self):
        """Test forbidden contains dangerous modules."""
        dangerous = [
            "os",
            "sys",
            "subprocess",
            "shutil",
            "ctypes",
            "socket",
            "exec",
            "eval",
            "compile",
            "pickle",
            "marshal",
        ]
        for module in dangerous:
            assert module in DEFAULT_FORBIDDEN, f"{module} should be forbidden"

    def test_allowed_contains_safe(self):
        """Test allowed contains safe modules."""
        safe = [
            "json",
            "re",
            "math",
            "random",
            "datetime",
            "time",
            "typing",
            "dataclasses",
            "enum",
            "hashlib",
            "asyncio",
        ]
        for module in safe:
            assert module in DEFAULT_ALLOWED, f"{module} should be allowed"

    def test_no_overlap(self):
        """Test forbidden and allowed don't overlap."""
        overlap = DEFAULT_FORBIDDEN & DEFAULT_ALLOWED
        assert len(overlap) == 0, f"Overlap found: {overlap}"
