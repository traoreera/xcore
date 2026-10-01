"""
Le budget CPU du worker sandboxed est PAR REQUÊTE, pas cumulatif.

RLIMIT_CPU compte le temps CPU total du processus : posé une fois à 10 s, il tuait
un worker parfaitement sain (SIGXCPU) après 10 s de CPU cumulées sur toute sa vie,
puis le plugin passait FAILED après `max_restarts` plantages. Ces tests tournent
dans un sous-processus : abaisser RLIMIT_CPU du process pytest le tuerait.
"""

import os
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from xcore.kernel.sandbox.process_manager import (
    ProcessState,
    SandboxConfig,
    SandboxProcessManager,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="RLIMIT_CPU n'existe pas sous Windows"
)

SCRIPT = textwrap.dedent("""
    import os, sys, time
    os.environ["_SANDBOX_MAX_CPU_SEC"] = "1"
    os.environ["_SANDBOX_MAX_CPU_LIFETIME_SEC"] = sys.argv[3]
    from xcore.kernel.sandbox import worker

    worker._apply_resource_limits()

    def burn(seconds):
        end = time.process_time() + seconds
        while time.process_time() < end:
            pass

    for _ in range(int(sys.argv[1])):
        worker._arm_cpu_budget()      # = avant chaque requête
        burn(float(sys.argv[2]))
    print("survived", worker._needs_recycle())
    """)


def _run(
    requests: int, burn_s: float, lifetime_s: int = 0
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", SCRIPT, str(requests), str(burn_s), str(lifetime_s)],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "LOG_LEVEL": "ERROR"},
    )


def test_cpu_cumulated_over_many_requests_does_not_kill_the_worker():
    # 5 requêtes de 0,6 s = 3 s de CPU au total, bien au-delà du budget de 1 s
    result = _run(requests=5, burn_s=0.6)

    assert result.returncode == 0, result.stderr
    assert "survived False" in result.stdout  # pas de plafond de vie configuré


def test_a_single_request_over_budget_is_still_killed():
    started = time.monotonic()
    result = _run(requests=1, burn_s=30)

    assert result.returncode == -signal.SIGXCPU
    assert time.monotonic() - started < 15


def test_worker_asks_to_be_recycled_before_the_lifetime_ceiling_is_hit(
    monkeypatch,
):
    """
    Plafond de vie 4 s, budget 1 s : dès que ≥ 2 s de CPU sont consommées la
    requête suivante ne pourrait plus avoir son budget complet (2 + 1 + 1 >= 4) —
    le worker doit demander son recyclage plutôt que d'être tué en pleine requête.
    Déterministe : la consommation CPU est simulée (aucune limite posée sur pytest).
    """
    from xcore.kernel.sandbox import worker

    monkeypatch.setattr(worker, "_cpu_budget_s", 1)
    monkeypatch.setattr(worker, "_cpu_lifetime_s", 4)

    for consumed, expected in ((0.2, False), (1.9, False), (2.0, True), (3.5, True)):
        monkeypatch.setattr(worker, "_cpu_consumed", lambda c=consumed: c)
        assert worker._needs_recycle() is expected, consumed

    monkeypatch.setattr(worker, "_cpu_lifetime_s", 0)  # aucun plafond configuré
    assert worker._needs_recycle() is False


def test_worker_does_not_recycle_while_far_from_the_ceiling():
    result = _run(requests=1, burn_s=0.2, lifetime_s=60)

    assert result.returncode == 0, result.stderr
    assert "survived False" in result.stdout


def test_recycle_exit_code_is_shared_between_worker_and_parent():
    from xcore.kernel.sandbox import process_manager, worker

    assert worker.RECYCLE_EXIT_CODE == process_manager.RECYCLE_EXIT_CODE == 75


class TestRestartCounterReset:
    @pytest.fixture
    def manager(self, tmp_path):
        from unittest.mock import AsyncMock, MagicMock

        manifest = MagicMock()
        manifest.name = "p"
        manifest.plugin_dir = tmp_path
        manifest.resources.max_disk_mb = 10
        manifest.resources.max_memory_mb = 128
        manifest.resources.timeout_seconds = 5
        manifest.env = {}
        manifest.runtime.health_check.enabled = False
        config = SandboxConfig(
            restart_delay=0.01, max_restarts=2, restart_reset_after=60.0
        )
        mgr = SandboxProcessManager(manifest, MagicMock(), config=config)
        mgr._process = MagicMock(returncode=None, wait=AsyncMock(return_value=1))
        mgr._state = ProcessState.RUNNING
        mgr._spawn = AsyncMock()
        return mgr

    async def test_crash_after_a_long_stable_run_starts_a_fresh_sequence(self, manager):
        manager._restarts = 2  # == max_restarts : serait FAILED sans le reset
        manager._started_at = time.monotonic() - 3600

        await manager._handle_crash()

        assert manager.state == ProcessState.RUNNING
        assert manager._restarts == 1

    async def test_crash_loop_is_still_capped(self, manager):
        manager._restarts = 2
        manager._started_at = time.monotonic() - 1  # vient de redémarrer

        await manager._handle_crash()

        assert manager.state == ProcessState.FAILED

    def test_cpu_limits_are_configurable(self):
        config = SandboxConfig()
        assert config.max_cpu_seconds == 10
        assert config.max_cpu_lifetime_seconds == 3600
        assert SandboxConfig(max_cpu_seconds=3).max_cpu_seconds == 3

    async def test_recycled_worker_is_restarted_without_counting_as_a_crash(
        self, manager
    ):
        from unittest.mock import AsyncMock

        from xcore.kernel.sandbox.isolation import RECYCLE_EXIT_CODE

        manager._process.wait = AsyncMock(return_value=RECYCLE_EXIT_CODE)
        manager._restarts = 2  # == max_restarts : un vrai plantage serait fatal
        manager._started_at = time.monotonic() - 1

        await manager._watch_loop()

        assert manager.state == ProcessState.RUNNING
        assert manager._restarts == 1  # le redémarrage lui-même, pas l'historique

    async def test_real_crash_exit_code_still_counts(self, manager):
        from unittest.mock import AsyncMock

        manager._process.wait = AsyncMock(return_value=-24)  # SIGXCPU
        manager._restarts = 2
        manager._started_at = time.monotonic() - 1

        await manager._watch_loop()

        assert manager.state == ProcessState.FAILED
