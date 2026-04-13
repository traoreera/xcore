"""
worker.py — Subprocess sandboxed : point d'entrée isolé.

Lancé par SandboxProcessManager comme subprocess séparé.
Lit des commandes JSON sur stdin, répond sur stdout.
Limite mémoire appliquée au démarrage via RLIMIT_AS.
Filesystem policy appliquée via FilesystemGuard.
"""

from __future__ import annotations

import asyncio
import builtins as _builtins_module
import contextlib
import importlib.machinery
import importlib.util
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(asctime)s [%(levelname)s] worker: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("xcore.worker")


# ─────────────────────────────────────────────────────────────────────────────
#  Limite mémoire
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
#  FilesystemGuard
# ─────────────────────────────────────────────────────────────────────────────

# Capture de builtins.open AVANT tout patch
builtins_open = _builtins_module.open


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

        # Sécurité : on valide que chaque chemin résolu reste dans le plugin_dir.
        # Cela empêche un manifeste malicieux de configurer un accès hors du bac à sable.
        def _resolve_safe(paths, default):
            results = []
            for p in paths or default:
                try:
                    resolved = (self._plugin_dir / p).resolve()
                    if resolved.is_relative_to(self._plugin_dir):
                        results.append(resolved)
                    else:
                        logger.warning(
                            f"[sandbox:SECURITY] Tentative de traversal via manifest : {p!r}")
                except Exception as e:
                    logger.warning(
                        f"[sandbox:SECURITY] Erreur résolution manifest path {p!r} : {e}")
            return results

        self._allowed = _resolve_safe(allowed_paths, ["data/"])
        self._denied = _resolve_safe(denied_paths, ["src/"])
        self._original_open = builtins_open  # sauvegarde avant patch
        self._in_guard = False

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
            with contextlib.suppress(ValueError):
                target.relative_to(denied)
                return False  # dans un chemin denied → bloqué
        # 2. Vérifie allowed
        for allowed in self._allowed:
            with contextlib.suppress(ValueError):
                target.relative_to(allowed)
                return True  # dans un chemin allowed → autorisé
        # 3. Fail-closed
        return False

    def install(self) -> None:
        """
        Installe le guard de sécurité sandbox.

        Couverture des vecteurs de contournement :

        Couche 1 — Filesystem (chemins)
            builtins.open, io.open, io.FileIO   — ouverture fichier standard
            os.open                             — syscall direct (FD bruts)
            os.fdopen                           — wrapping de FD bruts pré-ouverts
            pathlib.Path.open                   — API OO pathlib

        Couche 2 — Exécution dynamique (code injecté à l'exécution)
            builtins.exec                       — exec("import os; ...")
            builtins.eval                       — eval("__import__('os')...")
            builtins.compile                    — compile() puis exec(code)
            builtins.__import__                 — __import__("os")
              → remplacé par un import hook qui bloque os/sys/ctypes/subprocess/…

        Couche 3 — Chargement de modules (post-init)
            importlib.import_module             — importlib.import_module("os")
            importlib.util.spec_from_file_location — chargement .py arbitraire
            importlib.util.find_spec            — énumération des modules système

        Couche 4 — ctypes (accès mémoire / appels libc)
            ctypes.CDLL, ctypes.cdll            — chargement bibliothèques .so/.dll
            ctypes.pythonapi                    — appels C Python API directs
            ctypes.libc / ctypes.windll         — libc et Win32 API
            ctypes.cast, ctypes.memmove         — manipulation mémoire brute

        Logique : fail-closed sur chaque couche, log de chaque tentative bloquée.
        """
        import builtins
        import io
        import traceback as _traceback

        guard = self

        # ── Helpers internes ─────────────────────────────────────────────────

        def _block(label: str, *args) -> None:
            """Log + lève PermissionError avec stack trace pour audit."""
            # Disable guard during traceback/logging to avoid recursion
            was = guard._in_guard
            guard._in_guard = True
            try:
                stack = "".join(_traceback.format_stack()[:-1])
                logger.warning(
                    f"[sandbox:BLOCKED] {label}\n"
                    f"  args={args!r}\n"
                    f"  stack:\n{stack}"
                )
            finally:
                guard._in_guard = was
            raise PermissionError(
                f"[sandbox] {label} interdit dans le sandbox")

        # ── Couche 1 : Filesystem ─────────────────────────────────────────────

        import inspect
        from pathlib import Path as _Path

        def _guarded_op(func, label):
            sig = inspect.signature(func)
            pnames = {"path", "file", "src", "dst", "target", "name", "self"}

            def wrapper(*args, **kwargs):
                if guard._in_guard:
                    return func(*args, **kwargs)
                try:
                    bound = sig.bind_partial(*args, **kwargs).arguments
                    paths = [
                        v
                        for k, v in bound.items()
                        if k in pnames and isinstance(v, (str, os.PathLike))
                    ]
                except Exception:
                    paths = []
                guard._in_guard = True
                try:
                    for p in paths:
                        if not guard.is_allowed(p):
                            _block(f"{label}({p!r})")
                    return func(*args, **kwargs)
                finally:
                    guard._in_guard = False

            return wrapper

        builtins.open = io.open = _guarded_op(builtins.open, "open")
        os.fdopen = lambda *a, **k: _block("os.fdopen()")

        class _GuardedFileIO(io.FileIO):
            def __init__(self, file, *args, **kwargs):
                if not guard._in_guard and isinstance(file, (str, os.PathLike)):
                    if not guard.is_allowed(file):
                        _block(f"io.FileIO('{file}')")
                super().__init__(file, *args, **kwargs)

        io.FileIO = _GuardedFileIO

        for op in [
            "open",
            "remove",
            "unlink",
            "rmdir",
            "mkdir",
            "makedirs",
            "rename",
            "replace",
            "listdir",
            "scandir",
            "stat",
            "lstat",
            "chmod",
        ]:
            if hasattr(os, op):
                setattr(os, op, _guarded_op(getattr(os, op), f"os.{op}"))

        for op in [
            "open",
            "unlink",
            "rmdir",
            "mkdir",
            "rename",
            "replace",
            "stat",
            "lstat",
            "chmod",
            "touch",
            "exists",
            "is_file",
            "is_dir",
        ]:
            if hasattr(_Path, op):
                setattr(_Path, op, _guarded_op(
                    getattr(_Path, op), f"Path.{op}"))

        # ── Couche 2 : Exécution dynamique ────────────────────────────────────

        # Modules interdits dans un contexte sandbox — toute tentative d'import
        # dynamique vers ces modules est bloquée même si le code contourne l'AST
        # scan en passant le nom comme string à exec/eval/__import__.
        _FORBIDDEN_MODULES = frozenset(
            {
                "os",
                "sys",
                "subprocess",
                "shutil",
                "signal",
                "ctypes",
                "cffi",
                "mmap",
                "socket",
                "ssl",
                "http",
                "urllib",
                "httpx",
                "requests",
                "aiohttp",
                "websockets",
                "importlib",
                "imp",
                "builtins",
                "inspect",
                "gc",
                "tracemalloc",
                "dis",
                "tempfile",
                "glob",
                "pickle",
                "shelve",
                "marshal",
                "multiprocessing",
                "threading",
                "concurrent",
                "pty",
                "termios",
                "tty",
                "fcntl",
                "resource",
            }
        )

        _real_import = builtins.__import__

        def _guarded_import(name, *args, **kwargs):
            if guard._in_guard:
                return _real_import(name, *args, **kwargs)
            root = name.split(".")[0]
            if root in _FORBIDDEN_MODULES:
                _block(f"__import__('{name}')", name)
            return _real_import(name, *args, **kwargs)

        def _blocked_exec(code, *args, **kwargs):
            _block("exec()", type(code).__name__)

        def _blocked_eval(expr, *args, **kwargs):
            _block("eval()", type(expr).__name__)

        def _blocked_compile(source, *args, **kwargs):
            _block("compile()", type(source).__name__)

        def _blocked_input(prompt=None):
            _block("input()")

        builtins.__import__ = _guarded_import
        builtins.exec = _blocked_exec
        builtins.eval = _blocked_eval
        builtins.compile = _blocked_compile
        builtins.input = _blocked_input

        # ── Couche 3 : importlib post-chargement ──────────────────────────────

        import importlib as _importlib
        import importlib.util as _importlib_util

        _real_import_module = _importlib.import_module
        _real_spec_from_file = _importlib_util.spec_from_file_location
        _real_find_spec = _importlib_util.find_spec

        def _guarded_import_module(name, package=None):
            if guard._in_guard:
                return _real_import_module(name, package)
            root = name.lstrip(".").split(".")[0]
            if root in _FORBIDDEN_MODULES:
                _block(f"importlib.import_module('{name}')", name)
            return _real_import_module(name, package)

        def _guarded_spec_from_file(name, location=None, *args, **kwargs):
            if guard._in_guard:
                return _real_spec_from_file(name, location, *args, **kwargs)
            # Un plugin sandbox ne doit pas charger de .py arbitraire depuis le
            # système de fichiers hors de son propre namespace déjà établi.
            _block(
                f"importlib.util.spec_from_file_location('{name}', '{location}')")

        def _guarded_find_spec(name, *args, **kwargs):
            if guard._in_guard:
                return _real_find_spec(name, *args, **kwargs)
            root = name.split(".")[0]
            if root in _FORBIDDEN_MODULES:
                _block(f"importlib.util.find_spec('{name}')", name)
            return _real_find_spec(name, *args, **kwargs)

        _importlib.import_module = _guarded_import_module
        _importlib_util.spec_from_file_location = _guarded_spec_from_file
        _importlib_util.find_spec = _guarded_find_spec

        # ── Couche 4 : ctypes — blocage complet ───────────────────────────────
        # ctypes.CDLL/cdll déjà bloqués → on ferme les APIs restantes.

        with contextlib.suppress(ImportError):
            import ctypes as _ctypes
            import sys

            def _blocked_ctypes_api(label):
                def _inner(*args, **kwargs):
                    _block(f"ctypes.{label}()", args)

                return _inner

            # Chargement de bibliothèques natives
            _ctypes.CDLL = _blocked_ctypes_api("CDLL")
            _ctypes.cdll = _blocked_ctypes_api("cdll")
            _ctypes.PyDLL = _blocked_ctypes_api("PyDLL")
            if sys.platform == "win32":
                _ctypes.WinDLL = _blocked_ctypes_api("WinDLL")  # Windows
                _ctypes.OleDLL = _blocked_ctypes_api("OleDLL")  # Windows

            # Manipulation mémoire brute
            _ctypes.cast = _blocked_ctypes_api("cast")
            _ctypes.memmove = _blocked_ctypes_api("memmove")
            _ctypes.memset = _blocked_ctypes_api("memset")
            _ctypes.string_at = _blocked_ctypes_api("string_at")
            _ctypes.wstring_at = _blocked_ctypes_api("wstring_at")

            # Accès Python C-API et libc
            with contextlib.suppress(AttributeError):
                _ctypes.pythonapi = _blocked_ctypes_api("pythonapi")
            with contextlib.suppress(AttributeError):
                _ctypes.cdll.LoadLibrary = _blocked_ctypes_api(
                    "cdll.LoadLibrary")
        logger.debug(
            f"[sandbox] Guard installé (4 couches) — "
            f"allowed={[str(p) for p in self._allowed]}, "
            f"denied={[str(p) for p in self._denied]}"
        )

    def uninstall(self) -> None:
        """Restaure les builtins originaux (utile pour les tests)."""
        import builtins

        builtins.open = self._original_open
        # Note : Path.open ne peut pas être restauré facilement sans référence,
        # mais le subprocess se termine de toute façon après usage.


# ─────────────────────────────────────────────────────────────────────────────
#  Chargement du plugin — namespace isolé, sans sys.path global
# ─────────────────────────────────────────────────────────────────────────────


class _PluginImportHook:
    """
    Import hook (sys.meta_path) qui intercepte tous les imports d'un plugin
    et les résout EXCLUSIVEMENT depuis son propre src_dir.

    Chaque plugin obtient un préfixe de namespace unique :
        xcore_plugin_<uid>.<module_name>

    Cela garantit que deux plugins ayant tous les deux un `utils.py`
    n'entrent jamais en conflit : leurs modules vivent dans des namespaces
    distincts et ne polluent pas sys.path global.

    Cycle de vie :
        hook = _PluginImportHook(uid, src_dir)
        hook.install()       ← enregistre dans sys.meta_path
        ...charger le plugin...
        hook.uninstall()     ← retire de sys.meta_path (propre)
    """

    def __init__(self, uid: str, src_dir: Path) -> None:
        self._uid = uid
        self._src_dir = src_dir
        self._pkg_prefix = f"xcore_plugin_{uid}"

    # ── sys.meta_path interface ───────────────────────────────────────────────

    def find_module(self, fullname: str, path=None):
        """API legacy (Python < 3.4) — délègue à find_spec."""
        return self if self._owns(fullname) else None

    def find_spec(self, fullname: str, path, target=None):
        """API moderne — appelée par importlib."""
        if not self._owns(fullname):
            return None
        # Traduit xcore_plugin_<uid>.foo.bar → src_dir/foo/bar.py (ou package)
        # retire le préfixe + "."
        relative = fullname[len(self._pkg_prefix) + 1:]
        return self._spec_for(fullname, relative)

    # ── Résolution ────────────────────────────────────────────────────────────

    def _owns(self, fullname: str) -> bool:
        return fullname == self._pkg_prefix or fullname.startswith(
            f"{self._pkg_prefix}."
        )

    def _spec_for(self, fullname: str, relative: str):
        """
        Cherche `relative` comme module ou package dans src_dir.
        relative = ""       → package racine (src_dir/__init__.py ou namespace)
        relative = "foo"    → src_dir/foo.py  ou  src_dir/foo/__init__.py
        relative = "foo.bar"→ src_dir/foo/bar.py
        """
        if not relative:
            # Package racine namespace (pas de __init__.py requis)
            if spec := importlib.util.spec_from_file_location(
                fullname,
                origin=None,
                submodule_search_locations=[str(self._src_dir)],
            ):
                return spec

        parts = relative.split(".")
        base = self._src_dir.joinpath(*parts)

        # Cas 1 : package (dossier avec __init__.py)
        init = base / "__init__.py"
        if init.exists():
            spec = importlib.util.spec_from_file_location(
                fullname,
                location=str(init),
                submodule_search_locations=[str(base)],
            )
            return spec

        # Cas 2 : module simple (.py)
        module_file = base.with_suffix(".py")
        if module_file.exists():
            spec = importlib.util.spec_from_file_location(
                fullname,
                location=str(module_file),
            )
            return spec

        return None

    def load_module(self, fullname: str):
        """API legacy — utilisée si find_module() a retourné self."""
        if fullname in sys.modules:
            return sys.modules[fullname]
        relative = (
            fullname[len(self._pkg_prefix) + 1:]
            if fullname != self._pkg_prefix
            else ""
        )
        spec = self._spec_for(fullname, relative)
        if spec is None:
            raise ImportError(f"Module introuvable : {fullname}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        if spec.loader:
            spec.loader.exec_module(module)
        return module

    # ── Installation / désinstallation ────────────────────────────────────────

    def install(self) -> None:
        """Enregistre ce hook en tête de sys.meta_path."""
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
        # Crée le package namespace racine dans sys.modules
        if self._pkg_prefix not in sys.modules:
            root = importlib.util.module_from_spec(
                importlib.machinery.ModuleSpec(
                    self._pkg_prefix,
                    loader=None,
                    is_package=True,
                )
            )
            root.__path__ = [str(self._src_dir)]
            root.__package__ = self._pkg_prefix
            sys.modules[self._pkg_prefix] = root
        logger.debug(
            f"[{self._uid}] Import hook installé (src={self._src_dir})")

    def uninstall(self) -> None:
        """Retire ce hook et nettoie tous les modules du namespace."""
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        # Purge tous les modules enregistrés sous ce namespace
        to_remove = [
            k
            for k in sys.modules
            if k == self._pkg_prefix or k.startswith(f"{self._pkg_prefix}.")
        ]
        for key in to_remove:
            del sys.modules[key]
        logger.debug(
            f"[{self._uid}] Import hook retiré ({len(to_remove)} modules purgés)"
        )


def _load_plugin(plugin_dir: Path, manifest: "_PluginManifest"):
    """
    Charge la classe Plugin dans un namespace totalement isolé.

    L'entry point est lu depuis le manifest (plugin.yaml) — jamais hardcodé.
    Le src_dir est dérivé du dossier parent de l'entry point.

    Garanties :
    - sys.path global n'est JAMAIS modifié.
    - Tous les modules du plugin vivent sous xcore_plugin_<uid>.*
    - Deux plugins avec le même fichier (ex: utils.py) ne se conflictent pas.
    - Les imports relatifs (from .utils import ...) fonctionnent correctement.
    """
    import hashlib

    # Résolution de l'entry point depuis le manifest
    entry = (plugin_dir / manifest.entry_point).resolve()
    if not entry.exists():
        raise FileNotFoundError(
            f"Entry point introuvable : {entry}  "
            f"(entry_point={manifest.entry_point!r} dans plugin.yaml)"
        )

    # Le src_dir = dossier contenant l'entry point
    # ex: entry="plugins/foo/src/main.py" → src_dir="plugins/foo/src"
    # ex: entry="plugins/foo/app/core.py" → src_dir="plugins/foo/app"
    src_dir = entry.parent

    # UID déterministe basé sur le chemin absolu du plugin_dir
    # Note: Use sha256 for better security and to avoid MD5 (Bandit B324)
    uid = hashlib.sha256(str(plugin_dir.resolve()).encode()).hexdigest()[:12]
    pkg_name = f"xcore_plugin_{uid}"

    # Le nom du module principal reprend le stem du fichier entry point
    # ex: main.py → xcore_plugin_<uid>.main
    # ex: core.py → xcore_plugin_<uid>.core
    main_module_name = f"{pkg_name}.{entry.stem}"

    # Installe le hook AVANT d'exécuter quoi que ce soit
    hook = _PluginImportHook(uid, src_dir)
    hook.install()

    try:
        spec = importlib.util.spec_from_file_location(
            main_module_name,
            location=str(entry),
            submodule_search_locations=[str(src_dir)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Impossible de construire le spec pour {entry}")

        # __package__ correct pour que les imports relatifs (from .utils import X)
        # soient résolus via notre hook dans le bon namespace
        module = importlib.util.module_from_spec(spec)
        module.__package__ = pkg_name
        module.__name__ = main_module_name

        sys.modules[main_module_name] = module
        spec.loader.exec_module(module)

    except Exception:
        hook.uninstall()
        raise

    if not hasattr(module, "Plugin"):
        hook.uninstall()
        raise AttributeError(f"Classe Plugin() manquante dans {entry}")

    instance = module.Plugin()
    instance._import_hook = hook

    logger.info(
        f"Plugin chargé : {plugin_dir.name} "
        f"(entry={manifest.entry_point!r}) → namespace {pkg_name}"
    )
    return instance


@dataclass
class _PluginManifest:
    """
    Sous-ensemble du manifeste plugin.yaml nécessaire au worker.
    Seuls les champs utilisés par le subprocess sont lus ici —
    la validation complète reste du ressort du LifecycleManager côté core.
    """

    entry_point: str = "src/main.py"
    allowed_paths: list = field(default_factory=lambda: ["data/"])
    denied_paths: list = field(default_factory=lambda: ["src/"])


def _load_manifest(plugin_dir: Path) -> _PluginManifest:
    """
    Parse plugin.yaml (ou plugin.json) et retourne un _PluginManifest.

    Champs lus :
        entry_point              (str,  défaut "src/main.py")
        filesystem.allowed_paths (list, défaut ["data/"])
        filesystem.denied_paths  (list, défaut ["src/"])

    En cas d'erreur de lecture/parsing, retourne les valeurs par défaut
    plutôt que de crasher — le FilesystemGuard restera strict de toute façon.
    """
    manifest = _PluginManifest()

    for fname in ("plugin.yaml", "plugin.json"):
        manifest_path = plugin_dir / fname
        if not manifest_path.exists():
            continue
        try:
            return _extracted_from__load_manifest_20(fname, manifest_path, manifest)
        except Exception as e:
            logger.warning(f"Impossible de lire le manifeste ({fname}) : {e}")

    logger.warning(
        f"Aucun manifeste trouvé dans {plugin_dir} — valeurs par défaut")
    return manifest


# TODO Rename this here and in `_load_manifest`
def _extracted_from__load_manifest_20(fname, manifest_path, manifest):
    if fname.endswith(".yaml"):
        import yaml

        with open(manifest_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        import json as _json

        with open(manifest_path, encoding="utf-8") as f:
            raw = _json.load(f)

    if ep := raw.get("entry_point"):
        manifest.entry_point = ep.strip()

    fs = raw.get("filesystem", {})
    if ap := fs.get("allowed_paths"):
        manifest.allowed_paths = ap
    if dp := fs.get("denied_paths"):
        manifest.denied_paths = dp

    logger.debug(
        f"Manifeste chargé : entry_point={manifest.entry_point!r}, "
        f"allowed={manifest.allowed_paths}, denied={manifest.denied_paths}"
    )
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires IPC
# ─────────────────────────────────────────────────────────────────────────────


def _send(transport, data: dict) -> None:
    line = json.dumps(data) + "\n"
    transport.write(line.encode("utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
#  Boucle principale du worker
# ─────────────────────────────────────────────────────────────────────────────


async def _run(plugin_dir: Path) -> None:
    # 1. Lecture du manifeste (entry_point + filesystem policy)
    manifest = _load_manifest(plugin_dir)

    # 2. Installation du guard filesystem (AVANT tout chargement de code plugin)
    guard = FilesystemGuard(
        plugin_dir, manifest.allowed_paths, manifest.denied_paths)
    guard.install()

    # 3. Chargement du plugin dans son namespace isolé
    plugin = _load_plugin(plugin_dir, manifest)

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
            response = {"status": "error", "msg": str(
                e), "code": "handler_error"}

        _send(transport, response)

    if hasattr(plugin, "on_unload"):
        try:
            await plugin.on_unload()
        except Exception:
            pass

    # Nettoyage du hook d'import isolé
    if hasattr(plugin, "_import_hook"):
        plugin._import_hook.uninstall()

    logger.info("Worker arrêté")


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps(
            {"status": "error", "msg": "Usage : worker.py <plugin_dir>"}))
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
