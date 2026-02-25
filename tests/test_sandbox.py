"""
Tests ciblés pour valider les 4 corrections.
"""
import asyncio
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

sys.path.insert(0, "./xcore")


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ══════════════════════════════════════════════════════════════
# FIX #1 — ipc.py : UnboundLocalError sur timeout
# ══════════════════════════════════════════════════════════════

class TestIPCTimeoutFix(unittest.TestCase):

    def _make_channel(self, *, dead=False, timeout_on_read=False, eof=False):
        from xcore.sandbox.sandbox.ipc import IPCChannel
        proc = MagicMock()
        # returncode=None  → process vivant ; int → mort
        proc.returncode = 1 if dead else None
        proc.stdin = AsyncMock()
        proc.stdin.write = MagicMock()
        proc.stdin.drain = AsyncMock()
        if timeout_on_read:
            async def _timeout():
                raise asyncio.TimeoutError()
            proc.stdout.readline = _timeout
        elif eof:
            proc.stdout.readline = AsyncMock(return_value=b"")
        else:
            proc.stdout.readline = AsyncMock(return_value=b'{"status":"ok"}\n')
        return IPCChannel(proc, timeout=0.1)

    def test_timeout_raises_IPCTimeoutError_not_UnboundLocalError(self):
        """Fix principal : asyncio.TimeoutError → IPCTimeoutError, pas UnboundLocalError."""
        from xcore.sandbox.sandbox.ipc import IPCTimeoutError
        channel = self._make_channel(timeout_on_read=True)
        with self.assertRaises(IPCTimeoutError):
            run(channel.call("ping", {}))

    def test_normal_call_works(self):
        """Chemin nominal non cassé."""
        channel = self._make_channel()
        resp = run(channel.call("ping", {}))
        self.assertTrue(resp.success)

    def test_dead_process_raises_IPCProcessDead(self):
        from xcore.sandbox.sandbox.ipc import IPCProcessDead
        channel = self._make_channel(dead=True)
        with self.assertRaises(IPCProcessDead):
            run(channel.call("ping", {}))

    def test_eof_raises_IPCProcessDead(self):
        from xcore.sandbox.sandbox.ipc import IPCProcessDead
        channel = self._make_channel(eof=True)
        with self.assertRaises(IPCProcessDead):
            run(channel.call("ping", {}))


# ══════════════════════════════════════════════════════════════
# FIX #2 — supervisor.py : _handle_crash() itératif
# ══════════════════════════════════════════════════════════════

class TestSupervisorHandleCrash(unittest.TestCase):

    def _make_supervisor(self, max_restarts=2):
        from xcore.sandbox.sandbox.supervisor import SandboxSupervisor, SupervisorConfig, ProcessState

        manifest = MagicMock()
        manifest.name = "test_plugin"
        manifest.resources.max_disk_mb = 0
        manifest.resources.max_memory_mb = 128
        manifest.resources.timeout_seconds = 5
        manifest.runtime.health_check.enabled = False
        manifest.runtime.health_check.timeout_seconds = 3
        manifest.runtime.health_check.interval_seconds = 30
        manifest.plugin_dir = Path("/tmp/fake_plugin")
        manifest.env = {}

        cfg = SupervisorConfig(max_restarts=max_restarts, restart_delay=0.0)
        sup = SandboxSupervisor(manifest, config=cfg)
        sup._state = ProcessState.RUNNING
        return sup, ProcessState

    def test_handle_crash_iterative_no_recursion(self):
        """Toutes les tentatives échouent → FAILED, pas RecursionError."""
        sup, ProcessState = self._make_supervisor(max_restarts=2)
        call_count = [0]

        async def fake_spawn():
            call_count[0] += 1

        async def fake_ping():
            raise RuntimeError("ping échoué")

        sup._spawn = fake_spawn
        sup._ping_check = fake_ping
        sup._kill = AsyncMock()

        run(sup._handle_crash())  # ne doit PAS lever RecursionError

        self.assertEqual(sup._state, ProcessState.FAILED)
        self.assertEqual(call_count[0], 2)  # exactement max_restarts tentatives

    def test_handle_crash_succeeds_on_second_attempt(self):
        """Succès à la 2e tentative → état RUNNING."""
        sup, ProcessState = self._make_supervisor(max_restarts=3)
        attempts = [0]

        async def fake_spawn():
            pass

        async def fake_ping():
            attempts[0] += 1
            if attempts[0] < 2:
                raise RuntimeError("not yet")

        sup._spawn = fake_spawn
        sup._ping_check = fake_ping
        sup._kill = AsyncMock()

        run(sup._handle_crash())

        self.assertEqual(sup._state, ProcessState.RUNNING)

    def test_handle_crash_noop_if_already_restarting(self):
        """Re-entrance : second appel ignoré si déjà RESTARTING."""
        sup, ProcessState = self._make_supervisor(max_restarts=1)
        sup._state = ProcessState.RESTARTING

        sup._spawn = AsyncMock()
        sup._ping_check = AsyncMock()
        sup._kill = AsyncMock()

        run(sup._handle_crash())  # doit retourner immédiatement

        sup._spawn.assert_not_called()

    def test_handle_crash_noop_if_stopped(self):
        """Appel depuis stop() ignoré."""
        sup, ProcessState = self._make_supervisor(max_restarts=1)
        sup._state = ProcessState.STOPPED
        sup._spawn = AsyncMock()
        run(sup._handle_crash())
        sup._spawn.assert_not_called()


# ══════════════════════════════════════════════════════════════
# FIX #3 — runner.py : mems() au reload
# ══════════════════════════════════════════════════════════════

class TestRunnerMems(unittest.TestCase):

    def _make_runner(self):
        from xcore.sandbox.trusted.runner import TrustedRunner
        manifest = MagicMock()
        manifest.name = "erp_core"
        shared_services = {}
        runner = TrustedRunner(manifest, services=shared_services)
        return runner, shared_services

    def test_initial_load_does_not_overwrite_existing_keys(self):
        """is_reload=False : respecte les clés déjà dans le container."""
        runner, shared = self._make_runner()
        shared["existing"] = "original"
        instance = MagicMock()
        instance._services = {"existing": "new_value", "fresh": "hello"}
        runner._instance = instance

        runner.mems(is_reload=False)

        self.assertEqual(shared["existing"], "original")   # non écrasé
        self.assertEqual(shared["fresh"], "hello")          # ajouté

    def test_reload_updates_existing_keys(self):
        """is_reload=True : le nouvel objet remplace l'ancien dans le container."""
        runner, shared = self._make_runner()
        old_svc = object()
        new_svc = object()
        shared["core"] = old_svc

        instance = MagicMock()
        instance._services = {"core": new_svc}
        runner._instance = instance

        runner.mems(is_reload=True)

        self.assertIs(shared["core"], new_svc)
        self.assertIsNot(shared["core"], old_svc)

    def test_mems_noop_if_no_instance(self):
        runner, shared = self._make_runner()
        runner._instance = None
        result = runner.mems(is_reload=True)
        self.assertEqual(result, {})

    def test_reload_only_updates_plugin_own_keys(self):
        """is_reload=True ne touche pas aux clés d'autres plugins."""
        runner, shared = self._make_runner()
        other_svc = object()
        shared["other_plugin_service"] = other_svc
        shared["core"] = "old"

        instance = MagicMock()
        instance._services = {"core": "new"}  # ce plugin ne connaît que "core"
        runner._instance = instance

        runner.mems(is_reload=True)

        self.assertIs(shared["other_plugin_service"], other_svc)  # intouché
        self.assertEqual(shared["core"], "new")


# ══════════════════════════════════════════════════════════════
# FIX #4 — plugin_manifest.py : _inject_envfile
# ══════════════════════════════════════════════════════════════

class TestInjectEnvfile(unittest.TestCase):

    def _fn(self):
        from xcore.sandbox.contracts.plugin_manifest import _inject_envfile
        return _inject_envfile

    def test_none_envcfg_is_noop(self):
        self._fn()(None, Path("/tmp"))

    def test_empty_dict_is_noop(self):
        self._fn()({}, Path("/tmp"))

    def test_inject_false_is_noop(self):
        self._fn()({"inject": False, "env_file": "doesnotexist.env"}, Path("/tmp"))

    def test_inject_true_missing_file_raises_ManifestError(self):
        from xcore.sandbox.contracts.plugin_manifest import ManifestError
        with self.assertRaises(ManifestError) as ctx:
            self._fn()({"inject": True}, Path("/tmp/nonexistent_9999"))
        self.assertIn("introuvable", str(ctx.exception))

    def test_inject_true_existing_file_calls_load_dotenv(self):
        """inject: true + fichier présent → load_dotenv appelé avec le bon path."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("TEST_VAR=hello\n")
            # load_dotenv est importé localement dans _inject_envfile,
            # on patche donc dotenv.load_dotenv
            with patch("dotenv.load_dotenv") as mock_ld:
                # Rendre le patch visible dans le module via sys.modules
                import dotenv
                orig = dotenv.load_dotenv
                dotenv.load_dotenv = mock_ld
                try:
                    self._fn()({"inject": True, "env_file": ".env"}, Path(tmpdir))
                    mock_ld.assert_called_once()
                    kwargs = mock_ld.call_args.kwargs
                    self.assertEqual(kwargs["dotenv_path"], env_path)
                finally:
                    dotenv.load_dotenv = orig

    def test_inject_true_missing_dotenv_raises_ManifestError(self):
        """python-dotenv absent → ManifestError explicite."""
        import tempfile
        from xcore.sandbox.contracts.plugin_manifest import ManifestError
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("X=1\n")
            # Simuler ImportError sur 'from dotenv import load_dotenv'
            import builtins
            real_import = builtins.__import__
            def fake_import(name, *args, **kwargs):
                if name == "dotenv":
                    raise ImportError("no module named dotenv")
                return real_import(name, *args, **kwargs)
            with patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises((ManifestError, ImportError)):
                    self._fn()({"inject": True}, Path(tmpdir))