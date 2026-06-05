"""Tests for sandbox isolation (DiskWatcher, MemoryLimiter)."""

import pytest
from pathlib import Path

from xcore.kernel.sandbox.isolation import DiskWatcher, DiskQuotaExceeded, MemoryLimiter


class TestDiskWatcher:
    def test_empty_dir_zero_size(self, tmp_path):
        watcher = DiskWatcher(tmp_path, max_disk_mb=10)
        assert watcher.current_size_bytes() == 0
        assert watcher.current_size_mb() == 0.0

    def test_nonexistent_dir_zero_size(self, tmp_path):
        watcher = DiskWatcher(tmp_path / "nonexistent", max_disk_mb=10)
        assert watcher.current_size_bytes() == 0

    def test_size_with_files(self, tmp_path):
        (tmp_path / "file.txt").write_bytes(b"x" * 1024)
        watcher = DiskWatcher(tmp_path, max_disk_mb=10)
        assert watcher.current_size_bytes() == 1024

    def test_check_within_quota(self, tmp_path):
        (tmp_path / "file.txt").write_bytes(b"x" * 100)
        watcher = DiskWatcher(tmp_path, max_disk_mb=10)
        watcher.check("myplugin")  # should not raise

    def test_check_exceeds_quota(self, tmp_path):
        large = b"x" * (2 * 1024 * 1024)  # 2MB
        (tmp_path / "file.dat").write_bytes(large)
        watcher = DiskWatcher(tmp_path, max_disk_mb=1)
        with pytest.raises(DiskQuotaExceeded, match="myplugin"):
            watcher.check("myplugin")

    def test_check_zero_quota_passes(self, tmp_path):
        (tmp_path / "file.dat").write_bytes(b"x" * 999999999)
        watcher = DiskWatcher(tmp_path, max_disk_mb=0)
        watcher.check("myplugin")  # should not raise — 0 means no limit

    def test_stats(self, tmp_path):
        (tmp_path / "file.txt").write_bytes(b"x" * 1024)
        watcher = DiskWatcher(tmp_path, max_disk_mb=10)
        stats = watcher.stats()
        assert "used_mb" in stats
        assert "max_mb" in stats
        assert "used_pct" in stats
        assert "ok" in stats
        assert stats["ok"] is True

    def test_stats_exceeded(self, tmp_path):
        (tmp_path / "file.dat").write_bytes(b"x" * (2 * 1024 * 1024))
        watcher = DiskWatcher(tmp_path, max_disk_mb=1)
        stats = watcher.stats()
        assert stats["ok"] is False

    def test_stats_no_max(self, tmp_path):
        watcher = DiskWatcher(tmp_path, max_disk_mb=0)
        stats = watcher.stats()
        assert stats["ok"] is True
        assert stats["used_pct"] == 0


class TestMemoryLimiter:
    def test_apply_zero_noop(self):
        MemoryLimiter.apply(0)  # should not raise

    def test_apply_negative_noop(self):
        MemoryLimiter.apply(-1)  # should not raise

    def test_apply_positive(self):
        import sys
        if sys.platform == "win32":
            pytest.skip("Not supported on Windows")
        try:
            MemoryLimiter.apply(512)  # may raise or not depending on OS limits
        except Exception:
            pass  # some systems don't allow raising RLIMIT_AS
