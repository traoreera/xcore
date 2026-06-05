"""
Tests for PluginActivators.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from xcore.kernel.runtime.activator import ActivatorRegistry, TrustedActivator, SandboxedActivator
from xcore.kernel.api.contract import ExecutionMode

@pytest.fixture
def mock_loader():
    loader = MagicMock()
    loader._config.strict_trusted = False
    return loader

@pytest.fixture
def mock_manifest():
    manifest = MagicMock()
    manifest.name = "test_plugin"
    manifest.execution_mode = ExecutionMode.TRUSTED
    manifest.allowed_imports = []
    manifest.entry_point = "main.py"
    manifest.plugin_dir = "/tmp/p1"
    return manifest

@pytest.mark.asyncio
async def test_trusted_activator_success(mock_loader, mock_manifest):
    activator = TrustedActivator()

    with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", spec=True) as mock_lm_class:
        mock_lm = mock_lm_class.return_value
        mock_lm.start = AsyncMock()

        with patch("xcore.kernel.security.validation.ASTScanner.scan") as mock_scan:
            mock_scan.return_value = MagicMock(passed=True)

            res = await activator.activate(mock_manifest, mock_loader)

            assert res == mock_lm
            mock_lm.start.assert_called_once()

@pytest.mark.asyncio
async def test_sandboxed_activator_success(mock_loader, mock_manifest):
    activator = SandboxedActivator()
    mock_manifest.execution_mode = ExecutionMode.SANDBOXED

    with patch("xcore.kernel.sandbox.process_manager.SandboxProcessManager", spec=True) as mock_mgr_class:
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.start = AsyncMock()

        with patch("xcore.kernel.security.validation.ASTScanner.scan") as mock_scan:
            mock_scan.return_value = MagicMock(passed=True)

            res = await activator.activate(mock_manifest, mock_loader)

            assert res == mock_mgr
            mock_mgr.start.assert_called_once()

@pytest.mark.asyncio
async def test_sandboxed_activator_scan_failed(mock_loader, mock_manifest):
    activator = SandboxedActivator()

    with patch("xcore.kernel.security.validation.ASTScanner.scan") as mock_scan:
        mock_scan.return_value = MagicMock(passed=False)

        with pytest.raises(ValueError, match="Scan AST échoué"):
            await activator.activate(mock_manifest, mock_loader)

def test_activator_registry():
    registry = ActivatorRegistry()
    activator = TrustedActivator()
    registry.register(ExecutionMode.TRUSTED, activator)
    assert registry.get(ExecutionMode.TRUSTED) == activator
    assert registry.get(ExecutionMode.SANDBOXED) is None
