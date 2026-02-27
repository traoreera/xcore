"""
worker.py — Subprocess sandboxed : point d'entrée isolé.

Lancé par SandboxProcessManager comme subprocess séparé.
Lit des commandes JSON sur stdin, répond sur stdout.
Limite mémoire appliquée au démarrage via RLIMIT_AS.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(asctime)s [%(levelname)s] worker: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("xcore.worker")


def _apply_memory_limit() -> None:
    max_mb = int(os.environ.get("_SANDBOX_MAX_MEM_MB", "0"))
    if max_mb <= 0 or sys.platform == "win32":
        return
    try:
        import resource

        limit = max_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        logger.debug(f"Limite mémoire : {max_mb}MB")
    except Exception as e:
        logger.warning(f"Impossible d'appliquer RLIMIT_AS : {e}")


def _load_plugin(plugin_dir: Path):
    """Charge la classe Plugin depuis src/main.py."""
    entry = plugin_dir / "src" / "main.py"
    if not entry.exists():
        raise FileNotFoundError(f"Entry point introuvable : {entry}")

    src_dir = str(plugin_dir / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    spec = importlib.util.spec_from_file_location("plugin_main", entry)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger {entry}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "Plugin"):
        raise AttributeError(f"Classe Plugin() manquante dans {entry}")

    return module.Plugin()


async def _run(plugin_dir: Path) -> None:
    plugin = _load_plugin(plugin_dir)

    # Initialisation du plugin si supportée
    if hasattr(plugin, "on_load"):
        await plugin.on_load()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()

    # Connecte stdin/stdout à asyncio
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    transport, _ = await loop.connect_write_pipe(asyncio.BaseProtocol, sys.stdout)

    logger.info("Worker prêt — écoute sur stdin")

    while True:
        try:
            line = await reader.readline()
        except (asyncio.IncompleteReadError, EOFError):
            break

        if not line:
            break

        raw = line.decode("utf-8", errors="replace").strip()
        if not raw:
            continue

        response: dict
        try:
            msg = json.loads(raw)
            action = msg.get("action", "")
            payload = msg.get("payload", {})

            if action == "ping":
                response = {"status": "ok", "pong": True}
            elif action == "shutdown":
                response = {"status": "ok", "msg": "shutdown"}
                _send(transport, response)
                break
            else:
                result = await plugin.handle(action, payload)
                response = (
                    result
                    if isinstance(result, dict)
                    else {"status": "ok", "result": result}
                )

        except json.JSONDecodeError as e:
            response = {
                "status": "error",
                "msg": f"JSON invalide : {e}",
                "code": "json_error",
            }
        except Exception as e:
            logger.exception(f"Erreur handle({action})")
            response = {"status": "error", "msg": str(e), "code": "handler_error"}

        _send(transport, response)

    if hasattr(plugin, "on_unload"):
        try:
            await plugin.on_unload()
        except Exception:
            pass

    logger.info("Worker arrêté")


def _send(transport, data: dict) -> None:
    line = json.dumps(data) + "\n"
    transport.write(line.encode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "msg": "Usage : worker.py <plugin_dir>"}))
        sys.exit(1)

    _apply_memory_limit()

    plugin_dir = Path(sys.argv[1]).resolve()
    if not plugin_dir.is_dir():
        print(
            json.dumps(
                {"status": "error", "msg": f"plugin_dir introuvable : {plugin_dir}"}
            )
        )
        sys.exit(1)

    try:
        asyncio.run(_run(plugin_dir))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        sys.stderr.write(f"FATAL: {e}\n")
        sys.exit(1)
