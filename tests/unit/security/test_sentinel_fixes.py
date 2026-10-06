from xcore.kernel.security.validation import ASTScanner


def test_ast_scanner_blocks_new_forbidden_builtins(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    code = """
def leak_info():
    d = dir()
    v = vars()
    i = input("give me something")
    help(str)
"""
    (src_dir / "main.py").write_text(code)

    scanner = ASTScanner()
    result = scanner.scan(tmp_path)

    assert not result.passed
    error_msgs = "\n".join(result.errors)
    assert "built-in interdit : 'dir'" in error_msgs
    assert "built-in interdit : 'vars'" in error_msgs
    assert "built-in interdit : 'input'" in error_msgs
    assert "built-in interdit : 'help'" in error_msgs


def test_ast_scanner_blocks_new_forbidden_modules(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    code = """
import multiprocessing
import threading
import concurrent.futures
import pty
import termios
import tty
import fcntl
"""
    (src_dir / "main.py").write_text(code)

    scanner = ASTScanner()
    result = scanner.scan(tmp_path)

    assert not result.passed
    error_msgs = "\n".join(result.errors)
    assert "import interdit — 'multiprocessing'" in error_msgs
    assert "import interdit — 'threading'" in error_msgs
    assert "import interdit — 'concurrent.futures'" in error_msgs
    assert "import interdit — 'pty'" in error_msgs
    assert "import interdit — 'termios'" in error_msgs
    assert "import interdit — 'tty'" in error_msgs
    assert "import interdit — 'fcntl'" in error_msgs


def test_ast_scanner_blocks_reflection_forbidden_attributes(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    code = """
def check_func(f):
    c = f.__closure__
    d = f.__defaults__
    kd = f.__kwdefaults__
    fn = f.__func__
    s = f.__self__
    m = f.__module__
"""
    (src_dir / "main.py").write_text(code)

    scanner = ASTScanner()
    result = scanner.scan(tmp_path)

    assert not result.passed
    error_msgs = "\n".join(result.errors)
    assert "attribut interdit : '__closure__'" in error_msgs
    assert "attribut interdit : '__defaults__'" in error_msgs
    assert "attribut interdit : '__kwdefaults__'" in error_msgs
    assert "attribut interdit : '__func__'" in error_msgs
    assert "attribut interdit : '__self__'" in error_msgs
    assert "attribut interdit : '__module__'" in error_msgs
