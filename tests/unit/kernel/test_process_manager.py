"""
Tests for SandboxProcessManager.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xcore.kernel.sandbox.ipc import IPCProcessDead, IPCResponse, IPCTimeoutError
from xcore.kernel.sandbox.process_manager import (
    _STDERR_LEVEL_RE,
    ProcessState,
    SandboxConfig,
    SandboxProcessManager,
)


class _FakeStderr:
    """
    Simule asyncio.StreamReader.readline() pour tester _stderr_pump() sans
    subprocess réel : items est une liste de bytes (une "ligne" chacun,
    la dernière b"" simule l'EOF) ou d'exceptions à lever à cette itération.
    """

    def __init__(self, items):
        self._items = list(items)

    async def readline(self):
        if not self._items:
            return b""
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


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
    config = SandboxConfig(startup_timeout=0.1, restart_delay=0.01, max_restarts=2)
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
        mock_proc.stderr = _FakeStderr([b""])  # EOF immédiat, pump se termine seule
        mock_proc.wait = AsyncMock(return_value=0)
        mock_spawn.return_value = mock_proc

        with patch(
            "xcore.kernel.sandbox.ipc.IPCChannel.call", new_callable=AsyncMock
        ) as mock_call:
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

        with patch(
            "xcore.kernel.sandbox.ipc.IPCChannel.call", new_callable=AsyncMock
        ) as mock_call:
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
    manager._channel.call = AsyncMock(
        return_value=IPCResponse(success=True, data={"status": "ok", "result": "hi"})
    )

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
async def test_manager_call_process_dead_triggers_recycle(manager):
    """IPCProcessDead sur un appel doit déclencher le recyclage immédiatement."""
    manager._state = ProcessState.RUNNING
    manager._channel = MagicMock()
    manager._channel.call = AsyncMock(side_effect=IPCProcessDead("dead"))

    with patch.object(manager, "_handle_crash", new_callable=AsyncMock) as mock_crash:
        with pytest.raises(IPCProcessDead):
            await manager.call("ping", {})
        mock_crash.assert_called_once()


@pytest.mark.asyncio
async def test_manager_call_ipc_timeout_triggers_recycle(manager):
    """
    IPCTimeoutError (subprocess bloqué, pas mort) doit aussi déclencher le
    recyclage immédiat — avant ce fix, seul IPCProcessDead était catché ici
    et il fallait attendre le prochain _health_loop pour recycler.
    """
    manager._state = ProcessState.RUNNING
    manager._channel = MagicMock()
    manager._channel.call = AsyncMock(side_effect=IPCTimeoutError("no response"))

    with patch.object(manager, "_handle_crash", new_callable=AsyncMock) as mock_crash:
        with pytest.raises(IPCTimeoutError):
            await manager.call("ping", {})
        mock_crash.assert_called_once()


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
    manager._restarts = 0  # Start from 0 to allow one loop

    with patch.object(manager, "_spawn", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.side_effect = Exception("Spawn failed")

        await manager._handle_crash()

        assert manager.state == ProcessState.FAILED
        assert manager._restarts == 1


@pytest.mark.asyncio
async def test_stderr_pump_dispatches_by_level_and_survives_bad_line(manager):
    """
    _stderr_pump() doit : router chaque ligne vers le niveau logger indiqué
    par son bracket [LEVEL] (format worker.py), retomber en error() pour une
    ligne non structurée (traceback brut), et continuer à lire après une
    ValueError (ligne trop longue) au lieu de s'arrêter définitivement.
    """
    manager._process = MagicMock()
    manager._process.stderr = _FakeStderr(
        [
            b"2026-09-30 12:00:00,000 [INFO] worker: plugin loaded\n",
            b"2026-09-30 12:00:00,001 [ERROR] worker: boom\n",
            b"raw traceback line without brackets\n",
            ValueError("Separator is not found, and chunk exceed the limit"),
            b"2026-09-30 12:00:00,002 [DEBUG] worker: still alive after bad line\n",
            b"",
        ]
    )

    with patch("xcore.kernel.sandbox.process_manager.logger") as mock_logger:
        await manager._stderr_pump()

        mock_logger.info.assert_any_call(
            "subprocess stderr",
            plugin="test_plugin",
            line="2026-09-30 12:00:00,000 [INFO] worker: plugin loaded",
        )
        mock_logger.error.assert_any_call(
            "subprocess stderr",
            plugin="test_plugin",
            line="2026-09-30 12:00:00,001 [ERROR] worker: boom",
        )
        # Ligne non structurée -> error par défaut (pas warning), comme
        # l'ancien lecteur crash-time.
        mock_logger.error.assert_any_call(
            "subprocess stderr",
            plugin="test_plugin",
            line="raw traceback line without brackets",
        )
        # La ValueError est catchée et loggée à part, sans arrêter la pompe.
        assert mock_logger.warning.called
        # La ligne suivant la ValueError est bien lue -> pas de mort silencieuse.
        mock_logger.debug.assert_any_call(
            "subprocess stderr",
            plugin="test_plugin",
            line="2026-09-30 12:00:00,002 [DEBUG] worker: still alive after bad line",
        )


def test_worker_stderr_format_stays_compatible_with_level_regex():
    """
    _STDERR_LEVEL_RE parse le format de logging.basicConfig de worker.py pour
    router chaque ligne stderr vers le bon niveau. Si ce format change un
    jour, ce test doit casser bruyamment plutôt que de laisser tout le
    sandbox logging retomber silencieusement sur le niveau par défaut.
    """
    import inspect

    from xcore.kernel.sandbox import worker

    source = inspect.getsource(worker)
    assert "[%(levelname)s]" in source, (
        "worker.py logging format changed — update "
        "process_manager._STDERR_LEVEL_RE (or restore the bracketed "
        "levelname) to keep stderr level dispatch working"
    )
    rendered = "2026-01-01 00:00:00 [WARNING] worker: test"
    assert _STDERR_LEVEL_RE.search(rendered)
