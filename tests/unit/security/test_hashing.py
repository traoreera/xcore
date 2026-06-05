"""Tests for xcore.kernel.security.hashing."""

import pytest
import tempfile
from pathlib import Path

from xcore.kernel.security.hashing import (
    hash_file,
    hash_dir,
    hmac_sign,
    hmac_verify,
)


class TestHashFile:
    def test_returns_hex_string(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = hash_file(f)
        assert isinstance(result, str)
        assert len(result) == 64  # sha256 hex

    def test_deterministic(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content")
        assert hash_file(f) == hash_file(f)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert hash_file(f1) != hash_file(f2)

    def test_sha256_algorithm(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"")
        result = hash_file(f, algorithm="sha256")
        assert len(result) == 64

    def test_sha1_algorithm(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"data")
        result = hash_file(f, algorithm="sha1")
        assert len(result) == 40  # sha1 hex


class TestHashDir:
    def test_empty_dir(self, tmp_path):
        result = hash_dir(tmp_path)
        assert isinstance(result, str)

    def test_deterministic(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        assert hash_dir(tmp_path) == hash_dir(tmp_path)

    def test_different_files_different_hash(self, tmp_path):
        d1 = tmp_path / "d1"
        d2 = tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "a.py").write_text("x = 1")
        (d2 / "a.py").write_text("x = 2")
        assert hash_dir(d1) != hash_dir(d2)

    def test_ignores_pyc_files(self, tmp_path):
        (tmp_path / "module.py").write_text("pass")
        h1 = hash_dir(tmp_path)
        (tmp_path / "module.pyc").write_text("bytecode")
        h2 = hash_dir(tmp_path)
        assert h1 == h2

    def test_ignores_dotfiles(self, tmp_path):
        (tmp_path / "module.py").write_text("pass")
        h1 = hash_dir(tmp_path)
        (tmp_path / ".hidden").write_text("hidden")
        h2 = hash_dir(tmp_path)
        assert h1 == h2

    def test_ignores_pycache(self, tmp_path):
        (tmp_path / "module.py").write_text("pass")
        h1 = hash_dir(tmp_path)
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-312.pyc").write_bytes(b"compiled")
        h2 = hash_dir(tmp_path)
        assert h1 == h2

    def test_ignores_log_files(self, tmp_path):
        (tmp_path / "module.py").write_text("pass")
        h1 = hash_dir(tmp_path)
        (tmp_path / "app.log").write_text("log data")
        h2 = hash_dir(tmp_path)
        assert h1 == h2

    def test_ignores_md_files(self, tmp_path):
        (tmp_path / "module.py").write_text("pass")
        h1 = hash_dir(tmp_path)
        (tmp_path / "README.md").write_text("# Docs")
        h2 = hash_dir(tmp_path)
        assert h1 == h2


class TestHmac:
    def test_sign_returns_string(self):
        result = hmac_sign(b"data", b"secret")
        assert isinstance(result, str)

    def test_sign_deterministic(self):
        r1 = hmac_sign(b"data", b"secret")
        r2 = hmac_sign(b"data", b"secret")
        assert r1 == r2

    def test_verify_valid(self):
        sig = hmac_sign(b"payload", b"key")
        assert hmac_verify(b"payload", b"key", sig) is True

    def test_verify_invalid(self):
        sig = hmac_sign(b"payload", b"key")
        assert hmac_verify(b"tampered", b"key", sig) is False

    def test_verify_wrong_key(self):
        sig = hmac_sign(b"data", b"key1")
        assert hmac_verify(b"data", b"key2", sig) is False

    def test_sign_different_data_different_sig(self):
        s1 = hmac_sign(b"data1", b"key")
        s2 = hmac_sign(b"data2", b"key")
        assert s1 != s2
