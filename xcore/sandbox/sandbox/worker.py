"""
sandbox/worker.py
──────────────────
Boucle stdin/stdout sans connect_read_pipe.
Utilise asyncio.StreamReader branché sur sys.stdin.buffer directement
via loop.run_in_executor pour éviter le blocage.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path


def _apply_memory_limit() -> None:
    max_mb = int(os.environ.get("_SANDBOX_MAX_MEM_MB", "0"))
    if max_mb <= 0 or sys.platform == "win32":
        return
    try:
        import resource
        limit = max_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_DATA, (limit, limit))
    except Exception:
        pass


def _read_line_blocking() -> bytes:
    """Lit une ligne sur stdin.buffer — appelé dans un executor thread."""
    return sys.stdin.buffer.readline()


async def _main() -> None:
    _apply_memory_limit()

    if len(sys.argv) < 2:
        _write_error("worker.py requiert le chemin du plugin en argv[1]")
        return

    plugin_dir = Path(sys.argv[1]).resolve()
    src_dir    = plugin_dir / "src"

    if not src_dir.exists():
        _write_error(f"Répertoire src/ introuvable dans {plugin_dir}")
        return

    sys.path.insert(0, str(src_dir))

    try:
        import main as plugin_module
        plugin = plugin_module.Plugin()
    except Exception as e:
        _write_error(f"Impossible de charger le plugin : {e}\n{traceback.format_exc()}")
        return

    loop = asyncio.get_running_loop()

    # Boucle readline via executor — évite le blocage de l'event loop
    # et contourne les problèmes de connect_read_pipe sur certains OS
    while True:
        raw = await loop.run_in_executor(None, _read_line_blocking)

        if not raw:
            break  # EOF propre

        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _write_error(f"JSON invalide : {e}")
            continue

        action  = request.get("action", "")
        payload = request.get("payload", {})

        if not isinstance(payload, dict):
            _write_error("'payload' doit être un dict")
            continue

        try:
            result = await plugin.handle(action, payload)
            if not isinstance(result, dict):
                result = {"status": "ok", "result": result}
        except Exception:
            result = {"status": "error", "msg": traceback.format_exc()}

        _write(result)


def _write(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False), flush=True)


def _write_error(msg: str) -> None:
    _write({"status": "error", "msg": msg})


if __name__ == "__main__":
    asyncio.run(_main())