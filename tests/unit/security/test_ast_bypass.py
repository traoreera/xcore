import ast
from pathlib import Path

import pytest

from xcore.kernel.security.validation import (DEFAULT_ALLOWED,
                                              DEFAULT_FORBIDDEN,
                                              _SecurityVisitor)


class TestASTBypass:
    @pytest.fixture
    def visitor(self):
        return _SecurityVisitor(
            forbidden=DEFAULT_FORBIDDEN,
            allowed=DEFAULT_ALLOWED,
            filename="bypass.py",
            path=Path("/test/bypass.py"),
        )

    def test_pathlib_os_bypass(self, visitor):
        """Test that pathlib.os is blocked."""
        code = "import pathlib; pathlib.os.system('ls')"
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should have an error for 'os' attribute
        assert any(
            "accès interdit via attribut : 'os'" in e
            for e in visitor.errors
        )

    def test_importlib_sys_bypass(self, visitor):
        """Test that importlib.sys is blocked."""
        code = "import importlib; importlib.sys.exit(0)"
        tree = ast.parse(code)
        visitor.visit(tree)

        # Should have an error for 'sys' attribute
        assert any(
            "accès interdit via attribut : 'sys'" in e
            for e in visitor.errors
        )

    def test_nested_bypass(self, visitor):
        """Test that nested attribute access is blocked."""
        code = "import xcore; xcore.os.system('ls')"
        tree = ast.parse(code)
        visitor.visit(tree)

        assert any(
            "accès interdit via attribut : 'os'" in e
            for e in visitor.errors
        )

    def test_legitimate_attribute_access(self, visitor):
        """Test that legitimate attribute access is NOT blocked."""
        code = "import json; data = json.loads('{}')"
        tree = ast.parse(code)
        visitor.visit(tree)

        # loads is not in forbidden modules or forbidden attributes
        assert not any("loads" in e for e in visitor.errors)
