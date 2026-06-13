"""
Tests for PluginLoader.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xcore.kernel.api.contract import ExecutionMode
from xcore.kernel.runtime.loader import PluginLoader


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.config.directory = "/tmp/plugins"
    ctx.services.as_dict.return_value = {}
    ctx.events = MagicMock()
    ctx.hooks = MagicMock()
    ctx.registry = MagicMock()
    ctx.metrics = MagicMock()
    ctx.tracer = MagicMock()
    ctx.health = MagicMock()
    return ctx


@pytest.fixture
def loader(mock_ctx):
    return PluginLoader(mock_ctx)


@pytest.mark.asyncio
async def test_loader_init(loader):
    assert loader._handlers == {}
    assert ExecutionMode.TRUSTED in loader._activators._activators
    assert ExecutionMode.SANDBOXED in loader._activators._activators


@pytest.mark.asyncio
async def test_loader_load_all_empty(loader, mock_ctx):
    with patch("pathlib.Path.exists", return_value=False):
        res = await loader.load_all()
        assert res["loaded"] == []
        assert res["failed"] == []


@pytest.mark.asyncio
async def test_loader_load_all_success(loader, mock_ctx):
    m1 = MagicMock()
    m1.name = "p1"
    m1.requires = []
    m1.execution_mode = ExecutionMode.TRUSTED
    m1.version = "1.0.0"

    p1 = MagicMock(spec=Path)
    p1.is_dir.return_value = True
    p1.name = "p1"

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.iterdir", return_value=[p1]):
            with patch.object(
                loader._validator, "load_and_validate", return_value=(m1, True, "2.3.2")
            ):
                with patch.object(
                    loader, "_activate", new_callable=AsyncMock
                ) as mock_activate:
                    res = await loader.load_all()
                    assert "p1" in res["loaded"]
                    mock_activate.assert_called_once_with(m1)


@pytest.mark.asyncio
async def test_loader_load_single_not_found(loader):
    with patch("pathlib.Path.is_dir", return_value=False):
        with pytest.raises(FileNotFoundError):
            await loader.load("missing")


@pytest.mark.asyncio
async def test_loader_get_not_found(loader):
    with pytest.raises(KeyError, match="not_found"):
        loader.get("not_found")


@pytest.mark.asyncio
async def test_loader_status_empty(loader):
    assert loader.status() == []


@pytest.mark.asyncio
async def test_loader_shutdown_empty(loader):
    await loader.shutdown()
    assert loader._handlers == {}


@pytest.mark.asyncio
async def test_loader_collect_routers_empty(loader):
    assert loader.collect_plugin_routers() == []


@pytest.mark.asyncio
async def test_loader_collect_app_state_empty(loader):
    assert loader.collect_app_state() == []


@pytest.mark.asyncio
async def test_loader_unload(loader):
    handler = MagicMock()
    handler.stop = AsyncMock()
    loader._handlers["p1"] = handler

    await loader.unload("p1")
    assert "p1" not in loader._handlers
    handler.stop.assert_called_once()


@pytest.mark.asyncio
async def test_loader_unload_missing(loader):
    with pytest.raises(KeyError, match="p1"):
        await loader.unload("p1")


@pytest.mark.asyncio
async def test_loader_get_manifest_none(loader):
    assert loader.get_manifest("none") is None


from xcore.kernel.runtime.loader import PluginLoader, _topo_sort


def test_loader_topo_sort(loader):
    m1 = MagicMock()
    m1.name = "p1"
    m1.requires = []

    m2 = MagicMock()
    m2.name = "p2"
    dep = MagicMock()
    dep.name = "p1"
    m2.requires = [dep]

    ordered = _topo_sort([m2, m1])
    assert [m.name for m in ordered] == ["p1", "p2"]


def test_loader_topo_sort_circular(loader):
    m1 = MagicMock()
    m1.name = "p1"
    dep2 = MagicMock()
    dep2.name = "p2"
    m1.requires = [dep2]

    m2 = MagicMock()
    m2.name = "p2"
    dep1 = MagicMock()
    dep1.name = "p1"
    m2.requires = [dep1]

    with pytest.raises(ValueError, match="Circular"):
        _topo_sort([m1, m2])
