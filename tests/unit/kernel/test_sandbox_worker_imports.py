"""#316 — le worker sandbox ne charge que des modules feuilles."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import xcore.kernel.sandbox.worker as worker
from xcore.kernel.sandbox import codes, isolation

WORKER = Path(worker.__file__)

# Lancé comme le fait SandboxProcessManager : worker.py par son FICHIER, dans un
# interpréteur neuf. Imprime les modules lourds qui se sont retrouvés importés.
PROBE = textwrap.dedent("""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("worker_probe", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    sys.modules["worker_probe"] = module
    spec.loader.exec_module(module)
    module._leaf("xcore.kernel.yamlio")
    heavy = ("xcore", "fastapi", "pydantic", "starlette", "opentelemetry", "sqlalchemy")
    print(",".join(name for name in heavy if name in sys.modules))
    module.logger.warning("ready", plugin="probe")
    """)


def _run_probe() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", PROBE, str(WORKER)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_worker_started_by_file_imports_no_framework_package():
    result = _run_probe()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"imports lourds : {result.stdout.strip()}"


def test_leaf_logger_still_renders_structured_fields():
    """Le formateur feuille est bien celui du process principal : les kwargs sont rendus."""
    result = _run_probe()
    assert "ready" in result.stderr
    assert "plugin=probe" in result.stderr


def test_leaf_returns_the_regular_module_when_xcore_is_imported():
    import xcore.kernel.observability.logging as regular

    assert worker._leaf("xcore.kernel.observability.logging") is regular
    assert worker.get_logger is regular.get_logger


def test_recycle_exit_code_has_a_single_definition():
    assert isolation.RECYCLE_EXIT_CODE == codes.RECYCLE_EXIT_CODE == 75
    assert worker.RECYCLE_EXIT_CODE == 75


def test_leaf_modules_have_no_xcore_import():
    """Garde-fou : une feuille qui gagne un import relatif casse le worker lancé par fichier."""
    import ast

    root = Path(worker.__file__).resolve().parents[3]
    for dotted in (
        "xcore.kernel.observability.logging",
        "xcore.kernel.sandbox.codes",
        "xcore.kernel.yamlio",
    ):
        tree = ast.parse(
            root.joinpath(*dotted.split(".")).with_suffix(".py").read_text()
        )
        for node in tree.body:  # imports de niveau module seulement
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{dotted}: import relatif {node.module}"
                assert not (node.module or "").startswith("xcore"), dotted
            elif isinstance(node, ast.Import):
                assert not any(a.name.startswith("xcore") for a in node.names), dotted
