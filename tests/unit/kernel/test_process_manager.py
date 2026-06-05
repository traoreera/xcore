"""
Tests for SandboxProcessManager.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from xcore.kernel.sandbox.process_manager import SandboxProcessManager, SandboxConfig, ProcessState
from xcore.kernel.sandbox.ipc import IPCResponse, IPCProcessDead

@pytest.fixture
def mock_manifest(tmp_path):
    manifest = MagicMock()
    manifest.name = "test_plugin"
    manifest.plugin_dir = tmp_path
    manifest.resources.max_disk_mb = 10
    manifest.resources.max_memory_mb = 128
    manifest.resources.timeout_seconds = 5
    manifest.env = {}
    manifest.runtime.health_check.enabled = True
    manifest.runtime.health_check.interval_seconds = 0.1
    manifest.runtime.health_check.timeout_seconds = 0.1
    return manifest

@pytest.fixture
def mock_loader():
    loader = MagicMock()
    loader._events.emit_sync = MagicMock()
    return loader

@pytest.fixture
def manager(mock_manifest, mock_loader):
    config = SandboxConfig(
        startup_timeout=0.1,
        restart_delay=0.01,
        max_restarts=2
    )
    return SandboxProcessManager(mock_manifest, mock_loader, config=config)

@pytest.mark.asyncio
async def test_manager_init(manager, mock_manifest):
    assert manager.state == ProcessState.STOPPED
    assert manager.is_available is False
    assert manager.uptime is None
    assert manager.status()["name"] == "test_plugin"

@pytest.mark.asyncio
async def test_manager_start_success(manager, mock_manifest, mock_loader):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)
        mock_proc.pid = 1234
        mock_proc.returncode = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_spawn.return_value = mock_proc

        with patch("xcore.kernel.sandbox.ipc.IPCChannel.call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = IPCResponse(success=True, data={"status": "ok"})

            await manager.start()

            assert manager.state == ProcessState.RUNNING
            assert manager.is_available is True
            assert manager.uptime > 0
            mock_spawn.assert_called_once()
            mock_loader._events.emit_sync.assert_called()

@pytest.mark.asyncio
async def test_manager_start_timeout(manager, mock_manifest):
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_spawn:
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)
        mock_proc.pid = 1234
        mock_proc.returncode = None
        mock_proc.wait = AsyncMock(return_value=1)
        mock_spawn.return_value = mock_proc

        with patch("xcore.kernel.sandbox.ipc.IPCChannel.call", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = asyncio.TimeoutError()

            with pytest.raises(RuntimeError, match="Pas de réponse au ping"):
                await manager.start()

            assert manager.state == ProcessState.STARTING
            mock_proc.terminate.assert_called()

@pytest.mark.asyncio
async def test_manager_call_success(manager):
    # Setup running state
    manager._state = ProcessState.RUNNING
    manager._channel = MagicMock()
    manager._channel.call = AsyncMock(return_value=IPCResponse(success=True, data={"status": "ok", "result": "hi"}))

    # Execute
    res = await manager.call("hello", {"name": "world"})

    # Verify
    assert res == {"status": "ok", "result": "hi"}
    manager._channel.call.assert_called_with("hello", {"name": "world"})

@pytest.mark.asyncio
async def test_manager_call_not_available(manager):
    with pytest.raises(RuntimeError, match="non disponible"):
        await manager.call("ping", {})

@pytest.mark.asyncio
async def test_manager_stop(manager):
    manager._state = ProcessState.RUNNING
    manager._process = MagicMock()
    manager._process.returncode = None
    manager._process.wait = AsyncMock(return_value=0)
    manager._channel = MagicMock()
    manager._channel.close = AsyncMock()

    await manager.stop()

    assert manager.state == ProcessState.STOPPED
    manager._channel.close.assert_called_once()
    manager._process.terminate.assert_called()

@pytest.mark.asyncio
async def test_manager_handle_crash_restart_success(manager, mock_manifest):
    manager._state = ProcessState.RUNNING
    manager._restarts = 0
    manager._process = MagicMock()
    manager._process.returncode = None
    manager._process.wait = AsyncMock(return_value=1)

    with patch.object(manager, "_spawn", new_callable=AsyncMock) as mock_spawn:
        # Simulate crash
        await manager._handle_crash()

        assert manager.state == ProcessState.RUNNING
        assert manager._restarts == 1
        mock_spawn.assert_called_once()

@pytest.mark.asyncio
async def test_manager_handle_crash_max_restarts(manager, mock_manifest):
    manager._state = ProcessState.RUNNING
    manager.config.max_restarts = 1
    manager._restarts = 0 # Start from 0 to allow one loop

    with patch.object(manager, "_spawn", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.side_effect = Exception("Spawn failed")

        await manager._handle_crash()

        assert manager.state == ProcessState.FAILED
        assert manager._restarts == 1
