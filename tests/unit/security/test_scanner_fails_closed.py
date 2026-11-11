"""A security scanner must fail CLOSED: a file it cannot parse is not a file it found clean.

`ASTScanner.scan` has two import phases: the compiled `scanner_core` extension when it is built, the
Python AST otherwise. Only the Python one reported a syntax error — so with the compiled scanner
installed (the optimised, shipped configuration) a plugin whose source does not parse came back
`passed=True`, and none of its imports, builtins or forbidden attributes had been examined.

`_check_builtins_and_attrs` parses every file in BOTH phases, so that is where the parse failure is
now reported, and only when the import phase could not do it (no duplicate message).
"""

from pathlib import Path

import pytest

from xcore.kernel.security.validation import ASTScanner


def _plugin(tmp_path: Path, source: str) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(source)
    return tmp_path


class TestUnparsableIsRefused:
    def test_a_file_that_does_not_parse_fails_the_scan(self, tmp_path):
        result = ASTScanner().scan(_plugin(tmp_path, "def broken(\n  pass"))
        assert result.passed is False
        assert any("syntaxe" in e for e in result.errors)

    def test_it_is_said_once_not_twice(self, tmp_path):
        """Both phases parse the file; the operator must read one message, not two."""
        result = ASTScanner().scan(_plugin(tmp_path, "def broken(\n  pass"))
        assert len([e for e in result.errors if "syntaxe" in e]) == 1

    def test_the_verdict_does_not_depend_on_the_compiled_scanner(
        self, tmp_path, monkeypatch
    ):
        """The whole point: the C++ path and the Python path must agree on an unparsable file."""
        plugin = _plugin(tmp_path, "def broken(\n  pass")
        with_cpp = ASTScanner()
        without_cpp = ASTScanner()
        monkeypatch.setattr(without_cpp, "_cpp", None)
        assert with_cpp.scan(plugin).passed is without_cpp.scan(plugin).passed is False

    def test_a_sound_file_still_passes(self, tmp_path):
        result = ASTScanner().scan(
            _plugin(tmp_path, "import json\n\nVALUE = json.dumps({'a': 1})\n")
        )
        assert result.passed is True, result.errors
        assert result.errors == []

    @pytest.mark.parametrize("source", ["eval('1+1')", "exec('x = 1')"])
    def test_a_forbidden_builtin_in_a_sound_file_is_still_caught(
        self, tmp_path, source
    ):
        """The regression to avoid: reporting parse errors must not shadow the real checks."""
        result = ASTScanner().scan(_plugin(tmp_path, source))
        assert result.passed is False
        assert any("built-in interdit" in e for e in result.errors)
