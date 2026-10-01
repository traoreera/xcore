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
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from xcore.kernel.observability import get_logger
from xcore.kernel.observability.logging import _TextFormatter
from xcore.kernel.sandbox.isolation import RECYCLE_EXIT_CODE

# ContextVar par tâche asyncio — évite les race conditions entre coroutines
# qui partageraient le même FilesystemGuard (requis pour la sécurité sandbox).
_sandbox_in_guard: ContextVar[bool] = ContextVar("sandbox_in_guard", default=False)

# _TextFormatter (le même que le process principal, xcore/kernel/observability/
# logging.py) et non un simple format="..." : un basicConfig(format=...) plein
# texte ignore les champs structurés passés en kwargs (logger.info(msg, plugin=...))
# — ils sont attachés via extra={"xcore_ctx": ...} et seuls _TextFormatter/
# _JsonFormatter savent les rendre. Sans ça, ces champs étaient silencieusement
# perdus même une fois le niveau et le drainage stderr corrigés côté kernel.
_worker_handler = logging.StreamHandler(sys.stderr)
_worker_handler.setFormatter(_TextFormatter())
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    handlers=[_worker_handler],
)
logger = get_logger("xcore.worker")


# ─────────────────────────────────────────────────────────────────────────────
#  Limite mémoire
# ─────────────────────────────────────────────────────────────────────────────
def _apply_resource_limits() -> None:
    if sys.platform == "win32":
        return
    try:
        import resource

        # ── Mémoire ───────────────────────────────────────────────────────
        max_mb = int(os.environ.get("_SANDBOX_MAX_MEM_MB", "0"))
        if max_mb > 0:
            limit = max_mb * 1024 * 1024
            with contextlib.suppress(Exception):
                resource.setrlimit(resource.RLIMIT_DATA, (limit, limit))
            with contextlib.suppress(Exception):
                resource.setrlimit(resource.RLIMIT_RSS, (limit, limit))
            logger.debug("memory limit applied", max_mb=max_mb, resource="DATA+RSS")

        # ── CPU ───────────────────────────────────────────────────────────
        # RLIMIT_CPU compte le temps CPU CUMULÉ du processus depuis son
        # démarrage : posée une fois à 10 s, elle tuait (SIGXCPU — action par
        # défaut : terminer) tout worker sain après 10 s de CPU au total sur sa
        # vie, soit quelques minutes de requêtes ordinaires, puis le plugin
        # finissait FAILED après `max_restarts`. Deux niveaux à la place :
        #   - limite SOUPLE = budget PAR REQUÊTE, réarmée avant chaque appel à
        #     « CPU déjà consommé + budget » (_arm_cpu_budget) ;
        #   - limite DURE = plafond de CPU cumulé de la vie du worker (+ grace).
        #     Une limite dure ne peut jamais être relevée sans privilège, donc
        #     elle reste un filet côté noyau qu'un plugin ne peut pas contourner.
        #     Avant de l'atteindre le worker se recycle proprement
        #     (_needs_recycle → RECYCLE_EXIT_CODE) au lieu d'être tué.
        global _cpu_budget_s, _cpu_lifetime_s
        max_cpu_s = int(os.environ.get("_SANDBOX_MAX_CPU_SEC", "0"))
        if max_cpu_s > 0:
            _cpu_budget_s = max_cpu_s
            _cpu_lifetime_s = int(os.environ.get("_SANDBOX_MAX_CPU_LIFETIME_SEC", "0"))
            hard = _cpu_lifetime_s + 5 if _cpu_lifetime_s > 0 else None
            _arm_cpu_budget(hard)
            logger.debug(
                "cpu limits applied",
                per_request_s=_cpu_budget_s,
                lifetime_s=_cpu_lifetime_s,
            )

    except Exception as e:
        logger.warning("failed to apply resource limits", error=str(e))


# Budget CPU par requête et plafond cumulé du worker (secondes), 0 = illimité —
# voir _apply_resource_limits.
_cpu_budget_s: int = 0
_cpu_lifetime_s: int = 0

# Importé ici, AVANT l'installation des gardes d'import : `resource` est interdit
# au code du plugin, mais le worker en a besoin à chaque requête.
try:
    import resource as _resource
except ImportError:  # Windows
    _resource = None


def _cpu_consumed() -> float:
    usage = _resource.getrusage(_resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


def _arm_cpu_budget(hard: int | None = None) -> None:
    """
    Réarme la limite SOUPLE de RLIMIT_CPU à « CPU déjà consommé + budget ».

    `hard` n'est passé qu'au premier appel (il fixe la limite dure, irréversible) ;
    ensuite on garde celle déjà en place. Au dépassement de la limite souple le
    noyau envoie SIGXCPU ; sans handler (`signal` est interdit au plugin) c'est la
    fin du processus, que SandboxProcessManager détecte et relance.
    """
    if not _cpu_budget_s or _resource is None:
        return
    try:
        soft = int(_cpu_consumed()) + _cpu_budget_s + 1  # +1 : granularité 1 s
        if hard is None:
            _, hard = _resource.getrlimit(_resource.RLIMIT_CPU)
        if hard != _resource.RLIM_INFINITY:
            soft = min(soft, hard)
        _resource.setrlimit(_resource.RLIMIT_CPU, (soft, hard))
    except Exception as e:
        logger.debug("cannot re-arm cpu budget", error=str(e))


def _needs_recycle() -> bool:
    """
    Vrai quand la prochaine requête ne pourrait plus avoir son budget complet
    sous le plafond cumulé : mieux vaut se recycler (proprement, entre deux
    requêtes) que d'être tué en plein milieu de la suivante.
    """
    if not _cpu_lifetime_s or not _cpu_budget_s or _resource is None:
        return False
    try:
        return _cpu_consumed() + _cpu_budget_s + 1 >= _cpu_lifetime_s
    except Exception:
        return False


builtins_open = _builtins_module.open


def _install_subprocess_guard(block) -> None:
    """
    Bloque la création de subprocess quel que soit le chemin emprunté pour
    y accéder — pas seulement via `import` (couche 5 du sandbox).

    Patche directement les objets déjà en mémoire (`subprocess.Popen`,
    `os.fork`/`exec*`/`spawn*`, `asyncio.create_subprocess_*`) plutôt que de
    ne filtrer que les imports par nom : une classe déjà chargée par
    l'interpréteur (ex. `subprocess.Popen`, atteignable sans jamais exécuter
    `import subprocess` via `().__class__.__bases__[0].__subclasses__()`)
    resterait sinon exploitable même avec `subprocess` dans la liste des
    modules interdits. `block(label, *args)` est le callback `_block` de
    `FilesystemGuard._install_impl()` (log + lève `PermissionError`).
    """
    import asyncio as _asyncio
    import subprocess as _subprocess

    def _blocked_spawn(label):
        def _inner(*args, **kwargs):
            block(f"{label}()", args)

        return _inner

    def _blocked_popen_init(self, *args, **kwargs):
        block("subprocess.Popen()", args)

    _subprocess.Popen.__init__ = _blocked_popen_init
    _subprocess.call = _blocked_spawn("subprocess.call")
    _subprocess.run = _blocked_spawn("subprocess.run")
    _subprocess.check_call = _blocked_spawn("subprocess.check_call")
    _subprocess.check_output = _blocked_spawn("subprocess.check_output")

    for _name in (
        "fork",
        "forkpty",
        "system",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
    ):
        if hasattr(os, _name):
            setattr(os, _name, _blocked_spawn(f"os.{_name}"))

    async def _blocked_create_subprocess(*args, **kwargs):
        block("asyncio.create_subprocess_exec/_shell()", args)

    _asyncio.create_subprocess_exec = _blocked_create_subprocess
    _asyncio.create_subprocess_shell = _blocked_create_subprocess
    _asyncio.subprocess.create_subprocess_exec = _blocked_create_subprocess
    _asyncio.subprocess.create_subprocess_shell = _blocked_create_subprocess


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

        def _resolve_safe(paths, default):
            results = []
            for p in paths or default:
                try:
                    resolved = (self._plugin_dir / p).resolve()
                    if resolved.is_relative_to(self._plugin_dir):
                        results.append(resolved)
                    else:
                        logger.warning(
                            "sandbox path traversal attempt via manifest", path=repr(p)
                        )
                except Exception as e:
                    logger.warning(
                        "sandbox manifest path resolution error",
                        path=repr(p),
                        error=str(e),
                    )
            return results

        self._allowed = _resolve_safe(allowed_paths, ["data/"])
        self._denied = _resolve_safe(denied_paths, ["src/"])
        self._original_open = builtins_open

    @property
    def _in_guard(self) -> bool:
        return _sandbox_in_guard.get()

    @_in_guard.setter
    def _in_guard(self, value: bool) -> None:
        _sandbox_in_guard.set(value)

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

        for denied in self._denied:
            with contextlib.suppress(ValueError):
                target.relative_to(denied)
                return False
        for allowed in self._allowed:
            with contextlib.suppress(ValueError):
                target.relative_to(allowed)
                return True
        return False

    def install(self) -> None:
        """
        Installe le guard de sécurité sandbox (4 couches).

        FIX : _in_guard=True pendant toute la durée de install() pour que les
        imports internes du framework (importlib, io, inspect…) ne soient pas
        bloqués par le _guarded_import qu'on vient de poser.
        La méthode repasse à False à la fin — à partir de ce moment le code
        plugin s'exécute sous le guard complet.
        """
        self._in_guard = True
        try:
            self._install_impl()
        finally:
            self._in_guard = False

        logger.debug(
            "sandbox filesystem guard installed",
            layers=4,
            allowed=[str(p) for p in self._allowed],
            denied=[str(p) for p in self._denied],
        )

    def _install_impl(self) -> None:
        """
        Corps réel de install() — tous les imports sont faits ICI, avant que
        _guarded_import ne soit posé, pour éviter l'auto-blocage.
        Exécuté avec _in_guard=True (via install()).
        """
        import builtins
        import ctypes as _ctypes
        import importlib as _importlib
        import importlib.util as _importlib_util
        import inspect
        import io
        import traceback as _traceback
        from pathlib import Path as _Path

        guard = self

        # ── Helpers internes ─────────────────────────────────────────────────

        def _block(label: str, *args) -> None:
            """Log + lève PermissionError avec stack trace pour audit."""
            was = guard._in_guard
            guard._in_guard = True
            try:
                stack = "".join(_traceback.format_stack()[:-1])
                logger.warning(
                    f"[sandbox:BLOCKED] {label}\n  args={args!r}\n  stack:\n{stack}"
                )
            finally:
                guard._in_guard = was
            raise PermissionError(f"[sandbox] {label} interdit dans le sandbox")

        # ── Couche 1 : Filesystem ─────────────────────────────────────────────

        def _guarded_op(func, label):
            try:
                sig = inspect.signature(func)
                pnames = {"path", "file", "src", "dst", "target", "name", "self"}
            except (ValueError, TypeError):
                # Builtin C sans signature introspectable (ex: os.chmod, os.stat…)
                # Fallback : on considère le 1er argument positionnel comme le chemin
                sig = None
                pnames = None

            def wrapper(*args, **kwargs):
                if guard._in_guard:
                    return func(*args, **kwargs)

                if sig is not None:
                    try:
                        bound = sig.bind_partial(*args, **kwargs)
                        # apply_defaults() : sans ça, un appel qui compte sur
                        # une valeur par défaut (ex: os.listdir() -> cwd) a un
                        # bound.arguments vide et passait le guard sans aucune
                        # vérification.
                        bound.apply_defaults()
                        paths = [
                            v
                            for k, v in bound.arguments.items()
                            if k in pnames and isinstance(v, (str, os.PathLike))
                        ]
                    except Exception:
                        paths = []
                else:
                    # Fallback builtin : 1er arg positionnel = le chemin
                    paths = (
                        [args[0]]
                        if args and isinstance(args[0], (str, os.PathLike))
                        else []
                    )

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
            "symlink",
            "link",
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
            "symlink_to",
            "hardlink_to",
        ]:
            if hasattr(_Path, op):
                setattr(_Path, op, _guarded_op(getattr(_Path, op), f"Path.{op}"))

        # ── Couche 2 : Exécution dynamique ────────────────────────────────────

        _FORBIDDEN_MODULES = frozenset(
            {
                "os",
                "posix",  # module bas niveau sous os sur Unix — accès quasi équivalent
                "pwd",
                "grp",
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
        _real_exec = builtins.exec  # capture BEFORE patching
        _real_eval = builtins.eval
        _real_compile = builtins.compile

        def _guarded_import(name, *args, **kwargs):
            if guard._in_guard:
                return _real_import(name, *args, **kwargs)
            root = name.split(".")[0]
            if root in _FORBIDDEN_MODULES:
                _block(f"__import__('{name}')", name)
            return _real_import(name, *args, **kwargs)

        def _blocked_exec(code, *args, **kwargs):
            if guard._in_guard:
                return _real_exec(code, *args, **kwargs)
            _block("exec()", type(code).__name__)

        def _blocked_eval(expr, *args, **kwargs):
            if guard._in_guard:
                return _real_eval(expr, *args, **kwargs)
            _block("eval()", type(expr).__name__)

        def _blocked_compile(source, *args, **kwargs):
            if guard._in_guard:
                return _real_compile(source, *args, **kwargs)
            _block("compile()", type(source).__name__)

        def _blocked_input(prompt=None):
            _block("input()")

        builtins.__import__ = _guarded_import
        builtins.exec = _blocked_exec
        builtins.eval = _blocked_eval
        builtins.compile = _blocked_compile
        builtins.input = _blocked_input

        # ── Couche 3 : importlib post-chargement ──────────────────────────────

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
            _block(f"importlib.util.spec_from_file_location('{name}', '{location}')")

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

        with contextlib.suppress(ImportError):

            def _blocked_ctypes_api(label):
                def _inner(*args, **kwargs):
                    _block(f"ctypes.{label}()", args)

                return _inner

            _ctypes.CDLL = _blocked_ctypes_api("CDLL")
            _ctypes.cdll = _blocked_ctypes_api("cdll")
            _ctypes.PyDLL = _blocked_ctypes_api("PyDLL")
            if sys.platform == "win32":
                _ctypes.WinDLL = _blocked_ctypes_api("WinDLL")
                _ctypes.OleDLL = _blocked_ctypes_api("OleDLL")

            _ctypes.cast = _blocked_ctypes_api("cast")
            _ctypes.memmove = _blocked_ctypes_api("memmove")
            _ctypes.memset = _blocked_ctypes_api("memset")
            _ctypes.string_at = _blocked_ctypes_api("string_at")
            _ctypes.wstring_at = _blocked_ctypes_api("wstring_at")

            with contextlib.suppress(AttributeError):
                _ctypes.pythonapi = _blocked_ctypes_api("pythonapi")
            with contextlib.suppress(AttributeError):
                _ctypes.cdll.LoadLibrary = _blocked_ctypes_api("cdll.LoadLibrary")

        # ── Couche 5 : création de subprocess — blocage des primitives ────────
        # Complète les couches 1-4 : bloquer l'IMPORT d'un module ne suffit pas
        # si la classe/fonction dangereuse est déjà chargée en mémoire par
        # l'interpréteur (ex: `().__class__.__bases__[0].__subclasses__()`
        # retrouve `subprocess.Popen` sans jamais exécuter `import subprocess`)
        # ou si elle vit dans un module légitime qu'on ne peut pas bloquer en
        # entier (`asyncio` sert au worker lui-même pour sa boucle IPC — seules
        # ses fonctions de spawn de subprocess sont dangereuses).
        _install_subprocess_guard(_block)

    def uninstall(self) -> None:
        """Restaure les builtins originaux (utile pour les tests)."""
        import builtins

        builtins.open = self._original_open


# ─────────────────────────────────────────────────────────────────────────────
#  Chargement du plugin — namespace isolé, sans sys.path global
# ─────────────────────────────────────────────────────────────────────────────


class _PluginImportHook:
    """
    Import hook (sys.meta_path) qui intercepte tous les imports d'un plugin
    et les résout EXCLUSIVEMENT depuis son propre src_dir.
    """

    def __init__(self, uid: str, src_dir: Path) -> None:
        self._uid = uid
        self._src_dir = src_dir
        self._pkg_prefix = f"xcore_plugin_{uid}"

    def find_module(self, fullname: str, path=None):
        return self if self._owns(fullname) else None

    def find_spec(self, fullname: str, path, target=None):
        if not self._owns(fullname):
            return None
        relative = fullname[len(self._pkg_prefix) + 1 :]
        return self._spec_for(fullname, relative)

    def _owns(self, fullname: str) -> bool:
        return fullname == self._pkg_prefix or fullname.startswith(
            f"{self._pkg_prefix}."
        )

    def _spec_for(self, fullname: str, relative: str):
        if not relative:
            if spec := importlib.util.spec_from_file_location(
                fullname,
                origin=None,
                submodule_search_locations=[str(self._src_dir)],
            ):
                return spec

        parts = relative.split(".")
        base = self._src_dir.joinpath(*parts)

        init = base / "__init__.py"
        if init.exists():
            return importlib.util.spec_from_file_location(
                fullname,
                location=str(init),
                submodule_search_locations=[str(base)],
            )

        module_file = base.with_suffix(".py")
        if module_file.exists():
            return importlib.util.spec_from_file_location(
                fullname,
                location=str(module_file),
            )

        return None

    def load_module(self, fullname: str):
        if fullname in sys.modules:
            return sys.modules[fullname]
        relative = (
            fullname[len(self._pkg_prefix) + 1 :]
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

    def install(self) -> None:
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
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
        logger.debug("import hook installed", uid=self._uid, src=str(self._src_dir))

    def uninstall(self) -> None:
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        to_remove = [
            k
            for k in sys.modules
            if k == self._pkg_prefix or k.startswith(f"{self._pkg_prefix}.")
        ]
        for key in to_remove:
            del sys.modules[key]
        logger.debug(
            "import hook removed", uid=self._uid, purged_modules=len(to_remove)
        )


def _load_plugin(plugin_dir: Path, manifest: "_PluginManifest"):
    import hashlib

    entry = (plugin_dir / manifest.entry_point).resolve()
    if not entry.exists():
        raise FileNotFoundError(
            f"Entry point introuvable : {entry}  "
            f"(entry_point={manifest.entry_point!r} dans plugin.yaml)"
        )

    src_dir = entry.parent
    uid = hashlib.sha256(str(plugin_dir.resolve()).encode()).hexdigest()[:12]
    pkg_name = f"xcore_plugin_{uid}"
    main_module_name = f"{pkg_name}.{entry.stem}"

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
        "plugin loaded in sandbox",
        plugin=plugin_dir.name,
        entry=manifest.entry_point,
        namespace=pkg_name,
    )
    return instance


@dataclass
class _PluginManifest:
    entry_point: str = "src/main.py"
    allowed_paths: list = field(default_factory=lambda: ["data/"])
    denied_paths: list = field(default_factory=lambda: ["src/"])
    configuration: dict = field(default_factory=dict)


def _load_manifest(plugin_dir: Path) -> _PluginManifest:
    manifest = _PluginManifest()

    for fname in ("plugin.yaml", "plugin.json"):
        manifest_path = plugin_dir / fname
        if not manifest_path.exists():
            continue
        try:
            return _parse_manifest_file(fname, manifest_path, manifest)
        except Exception as e:
            logger.warning("cannot read manifest file", file=fname, error=str(e))

    logger.warning("no manifest found, using defaults", plugin_dir=str(plugin_dir))
    return manifest


def _parse_manifest_file(fname, manifest_path, manifest: _PluginManifest):
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

    if cp := raw.get("configuration", {}):
        manifest.configuration = cp

    logger.debug(
        "manifest loaded",
        entry_point=manifest.entry_point,
        allowed=manifest.allowed_paths,
        denied=manifest.denied_paths,
    )
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires IPC
# ─────────────────────────────────────────────────────────────────────────────


def _send(transport, data: dict) -> None:
    line = json.dumps(data) + "\n"
    transport.write(line.encode("utf-8"))


def _trace_id_from_carrier(carrier: dict | None) -> str | None:
    """
    Extrait le trace_id d'un carrier W3C traceparent transmis par le Core via
    l'enveloppe IPC. Parsing manuel — le SDK OpenTelemetry n'est pas dans la
    whitelist d'imports du sandbox (ASTScanner), donc pas importable ici.
    Format : "{version}-{trace_id}-{parent_id}-{flags}".
    """
    if not carrier:
        return None
    traceparent = carrier.get("traceparent")
    if not traceparent:
        return None
    parts = traceparent.split("-")
    return parts[1] if len(parts) == 4 else None


# ─────────────────────────────────────────────────────────────────────────────
#  Boucle principale du worker
# ─────────────────────────────────────────────────────────────────────────────


async def _run(plugin_dir: Path) -> bool:
    """Boucle du worker. Retourne True si le worker demande à être recyclé."""
    recycle = False
    # 1. Lecture du manifeste
    manifest = _load_manifest(plugin_dir)

    # 2. Installation du guard filesystem.
    # install() gère _in_guard=True pendant sa propre exécution via _install_impl(),
    # puis repasse à False — le guard est actif pour le code plugin dès la sortie.
    guard = FilesystemGuard(plugin_dir, manifest.allowed_paths, manifest.denied_paths)
    guard.install()

    # 3. Chargement du plugin.
    # FIX : _load_plugin() et _PluginImportHook._spec_for() appellent
    # importlib.util.spec_from_file_location (remplacé par la Couche 3).
    # Ce sont des appels framework → on passe en mode bypass le temps du chargement.
    guard._in_guard = True
    try:
        plugin = _load_plugin(plugin_dir, manifest)
    finally:
        guard._in_guard = False  # à partir d'ici : code plugin, restrictions actives

    plugin._config = manifest.configuration
    if hasattr(plugin, "on_load"):
        await plugin.on_load()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_running_loop()

    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    class _StdoutProtocol(asyncio.BaseProtocol):
        def connection_made(self, transport):
            pass

        def connection_lost(self, exc):
            pass

    transport, _ = await loop.connect_write_pipe(_StdoutProtocol, sys.stdout)

    logger.info("sandbox worker ready, listening on stdin")

    while True:
        try:
            line = await reader.readline()
        except (asyncio.IncompleteReadError, EOFError):
            break
        except ValueError as e:
            # Ligne IPC plus longue que la limite du StreamReader (défaut
            # 64 KiB) : readline() nettoie déjà son buffer interne avant de
            # relever cette ValueError. Sans ce catch, une seule requête trop
            # grosse tuait tout le worker (et donc toutes les requêtes en
            # cours/à venir pour ce plugin), pas seulement celle-là.
            logger.warning("ipc line too long, skipped", error=str(e))
            continue

        if not line:
            break

        raw = line.decode("utf-8", errors="replace").strip()
        if not raw:
            continue

        response: dict
        action = ""
        trace_id = None
        try:
            msg = json.loads(raw)
            action = msg.get("action", "")
            payload = msg.get("payload", {})
            trace_id = _trace_id_from_carrier(msg.get("trace_context"))

            if action == "ping":
                response = {"status": "ok", "pong": True}
            elif action == "shutdown":
                response = {"status": "ok", "msg": "shutdown"}
                _send(transport, response)
                break
            else:
                _arm_cpu_budget()
                result = await plugin.handle(action, payload)
                response = (
                    result
                    if isinstance(result, dict)
                    else {"status": "ok", "result": result}
                )

        except PermissionError as e:
            logger.error("sandbox filesystem violation", error=str(e))
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
            logger.exception("handler error", action=action, trace_id=trace_id)
            response = {"status": "error", "msg": str(e), "code": "handler_error"}

        _send(transport, response)

        if _needs_recycle():
            logger.info(
                "cpu ceiling nearly reached, recycling worker",
                consumed_s=round(_cpu_consumed(), 1),
                lifetime_s=_cpu_lifetime_s,
            )
            recycle = True
            break

    if hasattr(plugin, "on_unload"):
        try:
            await plugin.on_unload()
        except Exception as e:
            logger.debug("plugin on_unload failed", error=str(e))

    if hasattr(plugin, "_import_hook"):
        plugin._import_hook.uninstall()

    logger.info("sandbox worker stopped")
    return recycle


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    _apply_resource_limits()

    plugin_dir = Path(sys.argv[1]).resolve()
    if not plugin_dir.is_dir():
        sys.exit(1)

    try:
        if asyncio.run(_run(plugin_dir)):
            sys.exit(RECYCLE_EXIT_CODE)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        sys.stderr.write(f"FATAL: {e}\n")
        sys.exit(1)
