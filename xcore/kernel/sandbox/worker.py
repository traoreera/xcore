"""
worker.py — Subprocess sandboxed : point d'entrée isolé.

Lancé par SandboxProcessManager comme subprocess séparé.
Lit des commandes JSON sur stdin, répond sur stdout.
Limite mémoire appliquée au démarrage via RLIMIT_AS.
Filesystem policy appliquée via FilesystemGuard.
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


class FilesystemGuard:
    """
    Applique la politique filesystem déclarée dans le manifeste.

    allowed_paths : seuls ces chemins (relatifs au plugin_dir) sont accessibles.
    denied_paths  : ces chemins sont explicitement bloqués, même si dans allowed.

    Fonctionne en monkey-patching les builtins open() et pathlib.Path dans
    le sous-processus, de façon à intercepter tout accès fichier du plugin.

    Logique d'évaluation (premier match gagne) :
        1. Si le chemin est dans denied_paths  → BLOQUÉ
        2. Si le chemin est dans allowed_paths → AUTORISÉ
        3. Sinon                               → BLOQUÉ (fail-closed)
    """

    def __init__(
        self,
        plugin_dir: Path,
        allowed_paths: list[str],
        denied_paths: list[str],
    ) -> None:
        self._plugin_dir = plugin_dir.resolve()
        self._allowed = [
            (self._plugin_dir / p).resolve() for p in (allowed_paths or ["data/"])
        ]
        self._denied = [
            (self._plugin_dir / p).resolve() for p in (denied_paths or ["src/"])
        ]
        self._original_open = builtins_open  # sauvegarde avant patch

    def _resolve(self, path_arg) -> Path:
        """Résout un chemin en absolu depuis le cwd (plugin_dir)."""
        p = Path(path_arg)
        if not p.is_absolute():
            p = Path.cwd() / p
        return p.resolve()

    def is_allowed(self, path_arg) -> bool:
        """Retourne True si le chemin est autorisé selon la policy."""
        try:
            target = self._resolve(path_arg)
        except Exception:
            return False

        # 1. Vérifie denied en premier
        for denied in self._denied:
            try:
                target.relative_to(denied)
                return False  # dans un chemin denied → bloqué
            except ValueError:
                pass

        # 2. Vérifie allowed
        for allowed in self._allowed:
            try:
                target.relative_to(allowed)
                return True  # dans un chemin allowed → autorisé
            except ValueError:
                pass

        # 3. Fail-closed
        return False

    def install(self) -> None:
        """Installe le guard en remplaçant builtins.open, os.open, io.open, etc."""
        import builtins
        import os
        import io

        guard = self
        _real_open = builtins.open
        _real_os_open = os.open
        _real_io_open = io.open
        _real_fileio = io.FileIO

        def _guarded_open(file, mode="r", *args, **kwargs):
            # Autoriser stdin/stdout/stderr (int file descriptors)
            if isinstance(file, int):
                return _real_open(file, mode, *args, **kwargs)
            if not guard.is_allowed(file):
                raise PermissionError(
                    f"[sandbox] Accès fichier refusé : '{file}'. "
                    f"Chemins autorisés : {[str(p) for p in guard._allowed]}"
                )
            return _real_open(file, mode, *args, **kwargs)

        builtins.open = _guarded_open

        # Patch os.open (accès syscall direct)
        def _guarded_os_open(path, flags, mode=0o777, *, dir_fd=None):
            if not guard.is_allowed(path):
                raise PermissionError(
                    f"[sandbox] Accès fichier refusé (os.open) : '{path}'"
                )
            return _real_os_open(path, flags, mode, dir_fd=dir_fd)

        os.open = _guarded_os_open

        # Patch io.open (alias de builtins.open mais peut être importé directement)
        io.open = _guarded_open

        # Patch io.FileIO (classe de bas niveau pour les fichiers binaires)
        class _GuardedFileIO(_real_fileio):
            def __init__(self, file, *args, **kwargs):
                if isinstance(file, (str, os.PathLike)) and not guard.is_allowed(file):
                    raise PermissionError(
                        f"[sandbox] Accès fichier refusé (FileIO) : '{file}'"
                    )
                super().__init__(file, *args, **kwargs)

        io.FileIO = _GuardedFileIO

        # Patch pathlib.Path.open également
        from pathlib import Path as _Path
        _real_path_open = _Path.open

        def _guarded_path_open(self_path, mode="r", *args, **kwargs):
            if not guard.is_allowed(self_path):
                raise PermissionError(
                    f"[sandbox] Accès fichier refusé : '{self_path}'. "
                    f"Chemins autorisés : {[str(p) for p in guard._allowed]}"
                )
            return _real_path_open(self_path, mode, *args, **kwargs)

        _Path.open = _guarded_path_open

        # Bloquer ctypes (accès direct à la mémoire/libc)
        try:
            import ctypes
            ctypes._real_load_library = ctypes.CDLL if hasattr(ctypes, 'CDLL') else None

            def _blocked_ctypes(*args, **kwargs):
                raise PermissionError("[sandbox] ctypes interdit dans le sandbox")

            ctypes.CDLL = _blocked_ctypes
            ctypes.cdll = _blocked_ctypes
        except ImportError:
            pass

        logger.debug(
            f"FilesystemGuard installé — "
            f"allowed={[str(p) for p in self._allowed]}, "
            f"denied={[str(p) for p in self._denied]}"
        )

    def uninstall(self) -> None:
        """Restaure les builtins originaux (utile pour les tests)."""
        import builtins
        from pathlib import Path as _Path

        builtins.open = self._original_open
        # Note : Path.open ne peut pas être restauré facilement sans référence,
        # mais le subprocess se termine de toute façon après usage.


# Capture de builtins.open AVANT tout patch
import builtins as _builtins_module
builtins_open = _builtins_module.open


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


def _load_filesystem_config(plugin_dir: Path) -> tuple[list[str], list[str]]:
    """
    Lit allowed_paths et denied_paths depuis le manifeste du plugin.
    Retourne les valeurs par défaut si le manifeste est absent ou incomplet.
    """
    default_allowed = ["data/"]
    default_denied = ["src/"]

    for fname in ("plugin.yaml", "plugin.json"):
        manifest_path = plugin_dir / fname
        if not manifest_path.exists():
            continue
        try:
            if fname.endswith(".yaml"):
                import yaml
                with open(manifest_path, encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
            else:
                import json as _json
                with open(manifest_path, encoding="utf-8") as f:
                    raw = _json.load(f)

            fs = raw.get("filesystem", {})
            allowed = fs.get("allowed_paths", default_allowed)
            denied = fs.get("denied_paths", default_denied)
            return allowed, denied
        except Exception as e:
            logger.warning(f"Impossible de lire la filesystem config : {e}")

    return default_allowed, default_denied


async def _run(plugin_dir: Path) -> None:
    # 1. Lecture de la filesystem policy AVANT le chargement du plugin
    allowed_paths, denied_paths = _load_filesystem_config(plugin_dir)

    # 2. Installation du guard filesystem
    guard = FilesystemGuard(plugin_dir, allowed_paths, denied_paths)
    guard.install()

    # 3. Chargement du plugin (sous protection du guard)
    plugin = _load_plugin(plugin_dir)

    if hasattr(plugin, "on_load"):
        await plugin.on_load()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()

    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    # Utilisation d'un protocole concret pour stdout
    class _StdoutProtocol(asyncio.BaseProtocol):
        def connection_made(self, transport):
            pass
        def connection_lost(self, exc):
            pass

    transport, _ = await loop.connect_write_pipe(_StdoutProtocol, sys.stdout)

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

        except PermissionError as e:
            # Violation filesystem policy — log + réponse d'erreur sans crash
            logger.error(f"[sandbox] Violation filesystem : {e}")
            response = {
                "status": "error",
                "msg": str(e),
                "code": "filesystem_denied",
            }
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