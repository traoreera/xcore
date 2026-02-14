"""
sandbox/worker.py
──────────────────
Script exécuté DANS le subprocess isolé du plugin Sandboxed.
Ce fichier est le point d'entrée universel — il charge le plugin,
écoute stdin, appelle handle() et répond sur stdout.

NE PAS IMPORTER CE FICHIER DANS LE CORE.
Il est copié / référencé comme entry point du subprocess.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
import contextlib
from pathlib import Path


async def _main() -> None:
    # ── Résolution du répertoire plugin ────────────────────────
    # argv[1] = chemin absolu du plugin passé par supervisor._spawn()
    if len(sys.argv) < 2:
        _write_error("worker.py requiert le chemin du plugin en argv[1]")
        return

    plugin_dir = Path(sys.argv[1]).resolve()
    src_dir    = plugin_dir / "src"

    if not src_dir.exists():
        _write_error(f"Répertoire src/ introuvable dans {plugin_dir}")
        return

    # Ajoute src/ au path pour que `import main` fonctionne
    sys.path.insert(0, str(src_dir))

    # ── Chargement du plugin ───────────────────────────────────
    try:
        import main as plugin_module
        plugin = plugin_module.Plugin()
    except Exception as e:
        _write_error(f"Impossible de charger le plugin : {e}\n{traceback.format_exc()}")
        return

    # ── Boucle stdin/stdout async ──────────────────────────────
    loop     = asyncio.get_running_loop()
    reader   = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)

    await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

    while True:
        try:
            raw = await reader.readline()
        except Exception:
            break

        if not raw:
            break  # EOF — Core a fermé stdin proprement

        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        # ── Parsing de la requête ──────────────────────────────
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

        # ── Appel handle() ─────────────────────────────────────
        try:
            result = await plugin.handle(action, payload)
            if not isinstance(result, dict):
                result = {"status": "ok", "result": result}
        except Exception:
            result = {
                "status": "error",
                "msg":    traceback.format_exc(),
            }

        _write(result)


def _write(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False), flush=True)


def _write_error(msg: str) -> None:
    _write({"status": "error", "msg": msg})


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt as e :
        pass
    except Exception as e:
        _write_error(f"Crash : {e}\n{traceback.format_exc()}")
        sys.exit(1)