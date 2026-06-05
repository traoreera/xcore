
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import os
import signal
import subprocess
from xcore.cli.worker_cmd import (
    _ensure_dirs, _write_pid, _read_pid, _is_running, _stop_pid,
    _resolve_celery_app, _cmd_status, _cmd_stop, handle_worker
)

class TestWorkerCmdHelpers:
    @patch("pathlib.Path.mkdir")
    def test_ensure_dirs(self, mock_mkdir):
        _ensure_dirs()
        assert mock_mkdir.call_count == 2

    def test_write_read_pid(self, tmp_path):
        pid_file = tmp_path / "test.pid"
        _write_pid(pid_file, 1234)
        assert pid_file.read_text() == "1234"
        assert _read_pid(pid_file) == 1234

    def test_read_pid_missing(self, tmp_path):
        assert _read_pid(tmp_path / "nonexistent") is None

    def test_read_pid_invalid(self, tmp_path):
        pid_file = tmp_path / "invalid.pid"
        pid_file.write_text("abc")
        assert _read_pid(pid_file) is None

    @patch("os.kill")
    def test_is_running(self, mock_kill):
        assert _is_running(None) is False

        mock_kill.return_value = None
        assert _is_running(123) is True

        mock_kill.side_effect = ProcessLookupError()
        assert _is_running(123) is False

    @patch("xcore.cli.worker_cmd._read_pid")
    @patch("xcore.cli.worker_cmd._is_running")
    @patch("os.kill")
    @patch("time.sleep")
    def test_stop_pid(self, mock_sleep, mock_kill, mock_is_running, mock_read_pid, tmp_path):
        pid_file = tmp_path / "api.pid"
        pid_file.touch()

        # Case 1: Not running
        mock_read_pid.return_value = 123
        mock_is_running.return_value = False
        assert _stop_pid(pid_file, "API") is False
        assert not pid_file.exists()

        # Case 2: Running and stops
        pid_file.touch()
        mock_is_running.side_effect = [True, False]
        assert _stop_pid(pid_file, "API") is True
        mock_kill.assert_called_with(123, signal.SIGTERM)

    @patch("xcore.cli.worker_cmd._load_config")
    def test_resolve_celery_app(self, mock_load):
        mock_load.return_value = None
        assert _resolve_celery_app(None) == "xcore.services.xworker.main:app"

class TestWorkerCmdCommands:
    @patch("xcore.cli.worker_cmd._read_pid")
    @patch("xcore.cli.worker_cmd._is_running")
    @patch("rich.console.Console.print")
    def test_cmd_status(self, mock_print, mock_is_running, mock_read_pid):
        mock_read_pid.return_value = 123
        mock_is_running.return_value = True

        args = MagicMock()
        args.json = False
        _cmd_status(args)
        # Should print table
        assert mock_print.called

    @patch("xcore.cli.worker_cmd._stop_pid")
    def test_cmd_stop(self, mock_stop):
        args = MagicMock()
        args.target = "all"
        _cmd_stop(args)
        assert mock_stop.call_count == 2

    @patch("xcore.cli.worker_cmd._cmd_start")
    def test_handle_worker_start(self, mock_start):
        args = MagicMock()
        args.worker_subcommand = "start"
        handle_worker(args)
        mock_start.assert_called_once_with(args)

    @patch("rich.console.Console.print")
    def test_handle_worker_help(self, mock_print):
        args = MagicMock()
        args.worker_subcommand = None
        handle_worker(args)
        assert mock_print.called

    @patch("subprocess.Popen")
    @patch("rich.console.Console.print")
    def test_start_api(self, mock_print, mock_popen):
        from xcore.cli.worker_cmd import _start_api
        args = MagicMock()
        args.app = "main:app"
        args.host = "127.0.0.1"
        args.port = 8000
        args.loglevel = "info"
        args.workers = 1
        args.reload = False
        args.detach = False

        _start_api(args)
        assert mock_popen.called
        cmd = mock_popen.call_args[0][0]
        assert "uvicorn" in cmd
        assert "main:app" in cmd

    @patch("subprocess.Popen")
    @patch("rich.console.Console.print")
    def test_start_celery(self, mock_print, mock_popen):
        from xcore.cli.worker_cmd import _start_celery
        args = MagicMock()
        args.loglevel = "info"
        args.config = None
        args.queues = "default"
        args.concurrency = 4
        args.detach = False
        args.hostname = "worker1"

        _start_celery(args)
        assert mock_popen.called
        cmd = mock_popen.call_args[0][0]
        assert "celery" in cmd
        assert "worker" in cmd
        assert "worker1" in cmd

    @patch("xcore.cli.worker_cmd._start_api")
    @patch("xcore.cli.worker_cmd._start_celery")
    @patch("rich.console.Console.print")
    def test_cmd_start_detach(self, mock_print, mock_start_celery, mock_start_api):
        from xcore.cli.worker_cmd import _cmd_start
        args = MagicMock()
        args.target = "all"
        args.detach = True

        _cmd_start(args)
        mock_start_api.assert_called_once()
        mock_start_celery.assert_called_once()
