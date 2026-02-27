"""
Test fixtures and utilities.
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_plugin_dir():
    """Create a sample plugin directory."""
    with tempfile.TemporaryDirectory() as tmp:
        plugin_dir = Path(tmp) / "sample_plugin"
        plugin_dir.mkdir()

        # Create plugin.yaml
        (plugin_dir / "plugin.yaml").write_text(
            """
name: sample_plugin
version: 1.0.0
author: Test
execution_mode: trusted
entry_point: src/main.py
"""
        )

        # Create src directory
        src_dir = plugin_dir / "src"
        src_dir.mkdir()

        # Create main.py
        (src_dir / "main.py").write_text(
            """
from xcore.sdk import TrustedBase, ok

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        return ok(message="Hello from sample plugin")
"""
        )

        yield plugin_dir


@pytest.fixture
def mock_services():
    """Create mock services."""
    from unittest.mock import MagicMock

    return {
        "db": MagicMock(),
        "cache": MagicMock(),
        "scheduler": MagicMock(),
    }
