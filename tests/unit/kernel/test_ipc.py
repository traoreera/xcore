"""
Tests for xcore.kernel.sandbox.ipc
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from xcore.kernel.sandbox.ipc import (
    IPCChannel,
    IPCError,
    IPCProcessDead,
    IPCTimeoutError,
)


@pytest.fixture
def mock_process():
    process = MagicMock(spec=asyncio.subprocess.Process)
    process.stdin = MagicMock()
    process.stdin.write = MagicMock()
    process.stdin.drain = AsyncMock()
    process.stdin.close = MagicMock()
    process.stdin.wait_closed = AsyncMock()

    process.stdout = MagicMock()
    process.stdout.readline = AsyncMock()

    process.returncode = None
    return process


@pytest.mark.asyncio
async def test_ipc_call_success(mock_process):
    # Setup
    channel = IPCChannel(mock_process)
    mock_process.stdout.readline.return_value = b'{"status": "ok", "result": 42}\n'

    # Execute
    resp = await channel.call("test", {"key": "val"})

    # Verify
    assert resp.success is True
    assert resp.data["result"] == 42
    mock_process.stdin.write.assert_called_once()
    mock_process.stdin.drain.assert_called_once()

    # Check payload sent to stdin
    sent_data = json.loads(mock_process.stdin.write.call_args[0][0].decode().strip())
    assert sent_data["action"] == "test"
    assert sent_data["payload"] == {"key": "val"}


@pytest.mark.asyncio
async def test_ipc_call_timeout(mock_process):
    # Setup
    channel = IPCChannel(mock_process, timeout=0.1)
    mock_process.stdout.readline.side_effect = asyncio.TimeoutError()

    # Execute & Verify
    with pytest.raises(IPCTimeoutError, match="Pas de réponse dans 0.1s"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_process_dead_before_call(mock_process):
    # Setup
    mock_process.returncode = 1
    channel = IPCChannel(mock_process)

    # Execute & Verify
    with pytest.raises(IPCProcessDead, match="Subprocess mort"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_process_dies_during_write(mock_process):
    # Setup
    channel = IPCChannel(mock_process)
    mock_process.stdin.drain.side_effect = BrokenPipeError("Pipe broken")

    # Execute & Verify
    with pytest.raises(IPCProcessDead, match="Écriture stdin impossible"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_unexpected_eof(mock_process):
    # Setup
    channel = IPCChannel(mock_process)
    mock_process.stdout.readline.return_value = b""  # EOF

    # Execute & Verify
    with pytest.raises(IPCProcessDead, match="EOF inattendu sur stdout"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_invalid_json(mock_process):
    # Setup
    channel = IPCChannel(mock_process)
    mock_process.stdout.readline.return_value = b"not a json\n"

    # Execute & Verify
    with pytest.raises(IPCError, match="JSON invalide"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_response_too_large(mock_process):
    # Setup
    channel = IPCChannel(mock_process, max_output_size=10)
    mock_process.stdout.readline.return_value = (
        b'{"status": "ok", "very_long_key": "very_long_value"}\n'
    )

    # Execute & Verify
    with pytest.raises(IPCError, match="Réponse trop volumineuse"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_generic_read_error(mock_process):
    # Setup
    channel = IPCChannel(mock_process)
    mock_process.stdout.readline.side_effect = Exception("Read error")

    # Execute & Verify
    with pytest.raises(IPCError, match="Lecture stdout : Read error"):
        await channel.call("test", {})


@pytest.mark.asyncio
async def test_ipc_close(mock_process):
    # Setup
    channel = IPCChannel(mock_process)

    # Execute
    await channel.close()

    # Verify
    mock_process.stdin.close.assert_called_once()
    mock_process.stdin.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_ipc_close_error_ignored(mock_process):
    # Setup
    channel = IPCChannel(mock_process)
    mock_process.stdin.close.side_effect = Exception("Close error")

    # Execute & Verify (should not raise)
    await channel.close()
    mock_process.stdin.close.assert_called_once()
