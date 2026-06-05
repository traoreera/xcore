"""Tests for signature.py error paths."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


def _make_manifest(tmp_path, name="test_plugin", version="1.0.0", entry_point="src/main.py"):
    m = MagicMock()
    m.name = name
    m.version = version
    m.entry_point = entry_point
    m.plugin_dir = tmp_path
    return m


class TestShouldIgnore:
    def test_ignores_pyc(self, tmp_path):
        from xcore.kernel.security.signature import _should_ignore
        f = tmp_path / "main.pyc"
        f.write_bytes(b"")
        assert _should_ignore(f, tmp_path) is True

    def test_ignores_symlink(self, tmp_path):
        from xcore.kernel.security.signature import _should_ignore
        target = tmp_path / "real_file.py"
        target.write_text("x = 1")
        link = tmp_path / "link.py"
        link.symlink_to(target)
        assert _should_ignore(link, tmp_path) is True

    def test_normal_py_not_ignored(self, tmp_path):
        from xcore.kernel.security.signature import _should_ignore
        f = tmp_path / "main.py"
        f.write_text("x = 1")
        assert _should_ignore(f, tmp_path) is False


class TestVerifyPlugin:
    def test_verify_sig_file_missing(self, tmp_path):
        from xcore.kernel.security.signature import verify_plugin, SignatureError
        manifest = _make_manifest(tmp_path)
        with pytest.raises(SignatureError, match="manquante|absente"):
            verify_plugin(manifest, b"secret")

    def test_verify_sig_file_invalid_json(self, tmp_path):
        from xcore.kernel.security.signature import verify_plugin, SignatureError, SIG_FILENAME
        (tmp_path / SIG_FILENAME).write_text("INVALID JSON {")
        manifest = _make_manifest(tmp_path)
        with pytest.raises(SignatureError, match="illisible"):
            verify_plugin(manifest, b"secret")

    def test_verify_missing_digest(self, tmp_path):
        from xcore.kernel.security.signature import verify_plugin, SignatureError, SIG_FILENAME
        (tmp_path / SIG_FILENAME).write_text(json.dumps({"version": "1.0.0"}))
        manifest = _make_manifest(tmp_path)
        with pytest.raises(SignatureError, match="digest"):
            verify_plugin(manifest, b"secret")

    def test_verify_version_mismatch(self, tmp_path):
        from xcore.kernel.security.signature import verify_plugin, SignatureError, SIG_FILENAME
        sig_data = {"version": "2.0.0", "digest": "abc123"}
        (tmp_path / SIG_FILENAME).write_text(json.dumps(sig_data))
        manifest = _make_manifest(tmp_path, version="1.0.0")
        with pytest.raises(SignatureError, match="mismatch"):
            verify_plugin(manifest, b"secret")

    def test_sign_and_verify_round_trip(self, tmp_path):
        from xcore.kernel.security.signature import sign_plugin, verify_plugin, SIG_FILENAME
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("class Plugin: pass")
        manifest = _make_manifest(tmp_path, entry_point="src/main.py")
        sign_plugin(manifest, b"my_secret")
        assert (tmp_path / SIG_FILENAME).exists()
        # Verification should pass
        verify_plugin(manifest, b"my_secret")

    def test_verify_invalid_signature(self, tmp_path):
        from xcore.kernel.security.signature import sign_plugin, verify_plugin, SignatureError
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("class Plugin: pass")
        manifest = _make_manifest(tmp_path, entry_point="src/main.py")
        sign_plugin(manifest, b"original_secret")
        with pytest.raises(SignatureError):
            verify_plugin(manifest, b"different_secret")
