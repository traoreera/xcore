"""
Tests for the tmp-dir cleanup safety net in tests/conftest.py.
"""

import tempfile
from pathlib import Path

from conftest import sweep_stray_tmp_dirs


def test_sweeps_stray_xcore_test_dirs():
    stray = Path(tempfile.mkdtemp(prefix="xcore_test_leftover_"))
    (stray / "marker.txt").write_text("leftover")
    assert stray.exists()

    sweep_stray_tmp_dirs()

    assert not stray.exists()


def test_does_not_touch_unrelated_tmp_dirs():
    unrelated = Path(tempfile.mkdtemp(prefix="not_xcore_related_"))
    try:
        sweep_stray_tmp_dirs()
        assert unrelated.exists()
    finally:
        unrelated.rmdir()


def test_temp_dir_fixture_uses_distinguishing_prefix(temp_dir):
    assert temp_dir.name.startswith("xcore_test_")
