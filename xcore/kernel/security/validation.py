"""
validation.py — Validation des manifestes et scan AST des plugins.

Scan des imports : C++ (scanner_core) avec fallback Python pur.
  - ImportClassifier C++ : O(1) pour forbidden/allowed, I/O multithread.
  - Fallback Python      : même logique, activé si le .so n'est pas compilé.

Correctifs manifeste :
  - allowed_imports peut contenir des noms de symboles (UTC, UUID, Mapped…) :
    ils sont silencieusement ignorés — seuls les noms de modules comptent.
  - Les modules locaux (src/) sont auto-détectés et jamais signalés.
  - Les wildcards (sqlalchemy.*, schemas.*) sont correctement résolus.
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from xcore.sdk.plugin_base import PluginDependency

from .section import (DEFAULT_ALLOWED, DEFAULT_FORBIDDEN, FORBIDDEN_ATTRIBUTES,
                      FORBIDDEN_BUILTINS, ScanResult, _SimpleManifest)

# ── Chargement de l'extension C++ (optionnel) ────────────────

try:
    from .scanner_core import \
        ImportClassifier as _CppClassifier  # type: ignore
    _CPP_AVAILABLE = True
except ImportError:
    _CppClassifier = None
    _CPP_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
# Manifest
# ─────────────────────────────────────────────────────────────


class ManifestError(Exception):
    pass


_ENV_VAR_RE = re.compile(r"^\$\{(.+)\}$")

# Détecte un "vrai" nom de module Python :
#   - commence par une minuscule ou un underscore
#   - ne contient pas de majuscule seule (UTC, UUID, Mapped…)
# On l'utilise pour filtrer les symboles/classes dans allowed_imports.
_MODULE_NAME_RE = re.compile(r"^[a-z_][\w]*(?:\.[\w]+)*(?:\.\*)?$")


def _looks_like_module(name: str) -> bool:
    """
    Retourne True si `name` ressemble à un module Python importable.

    Règle simple : commence par une minuscule ou un underscore.
    Rejette les noms de classe/symbole purs (UTC, UUID, TokenVerifyRequest…).
    Accepte les wildcards (sqlalchemy.*, schemas.*).
    """
    return bool(_MODULE_NAME_RE.match(name))


def _resolve_env(value: str) -> str:
    m = _ENV_VAR_RE.match(str(value))
    if not m:
        return str(value)
    var = m.group(1)
    resolved = os.environ.get(var)
    if resolved is None:
        raise ManifestError(
            f"Variable d'environnement '{var}' absente de l'environnement."
        )
    return resolved


class ManifestValidator:
    """Charge, valide et parse un manifeste plugin.yaml / plugin.json."""

    def load_and_validate(self, plugin_dir: Path):
        from xcore import __version__

        from ..api import ExecutionMode, check_compatibility

        plugin_dir = Path(plugin_dir).resolve()
        raw = self._read_raw(plugin_dir)

        for field_name in ("name", "version"):
            if not raw.get(field_name):
                raise ManifestError(
                    f"Champ obligatoire manquant : '{field_name}'")

        check_compatibility(
            raw.get("framework_version", f"=={__version__}"), __version__
        )

        raw_mode = raw.get("execution_mode", "legacy").lower()
        try:
            mode = ExecutionMode(raw_mode)
        except ValueError as e:
            raise ManifestError(
                f"execution_mode invalide : {raw_mode!r}. "
                f"Valeurs : {[m.value for m in ExecutionMode]}"
            ) from e

        self._inject_dotenv(raw.get("envconfiguration"), plugin_dir)
        resolved_env = {k: _resolve_env(v)
                        for k, v in raw.get("env", {}).items()}

        requires_raw = raw.get("requires", []) or []
        if not isinstance(requires_raw, list):
            raise ManifestError("'requires' doit être une liste")

        requires = []
        for dep in requires_raw:
            try:
                requires.append(PluginDependency.from_raw(dep))
            except ValueError as e:
                raise ManifestError(f"Dépendance invalide: {e}") from e

        return _build_manifest(raw, mode, resolved_env, requires, plugin_dir)

    def _read_raw(self, plugin_dir: Path) -> dict:
        for fname, loader in [("plugin.yaml", self._yaml), ("plugin.json", self._json)]:
            p = plugin_dir / fname
            if p.exists():
                return loader(p)
        raise ManifestError(f"Aucun manifeste dans {plugin_dir}")

    @staticmethod
    def _yaml(path: Path) -> dict:
        try:
            import yaml  # type: ignore

            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError as e:
            raise ManifestError("pyyaml non installé") from e

    @staticmethod
    def _json(path: Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _inject_dotenv(cfg: dict | None, plugin_dir: Path) -> None:
        if not cfg or not cfg.get("inject", False):
            return
        env_file = cfg.get("env_file", ".env")
        env_path = (plugin_dir / env_file).resolve()
        if not env_path.is_relative_to(plugin_dir.resolve()):
            raise ManifestError(
                f"Tentative de traversal via env_file : {env_file!r}")
        if not env_path.exists():
            raise ManifestError(
                f"envconfiguration.inject=true mais '{env_path}' introuvable."
            )
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=env_path, override=False)
        except ImportError as e:
            raise ManifestError("python-dotenv non installé") from e


def _build_manifest(raw, mode, resolved_env, requires, plugin_dir):
    try:
        from ...sdk.plugin_base import PluginManifest
    except ImportError:
        return _SimpleManifest(raw, mode, resolved_env, requires, plugin_dir)
    return PluginManifest.from_raw(raw, mode, resolved_env, requires, plugin_dir)


# ─────────────────────────────────────────────────────────────
# Normalisation des allowed_imports du manifeste
# ─────────────────────────────────────────────────────────────


def _parse_allowed_imports(raw_list: list[str]) -> tuple[set[str], list[str]]:
    """
    Sépare la liste `allowed_imports` du manifeste en :
      - exact  : set de modules autorisés en exact  (ex: "sqlalchemy", "uuid")
      - prefixes: liste de préfixes wildcard sans ".*" (ex: "sqlalchemy", "schemas")

    Les entrées qui ressemblent à des noms de classe/symbole (UTC, UUID, Mapped…)
    sont silencieusement ignorées — elles ne correspondent à aucun module source
    et génèreraient des faux positifs si elles étaient passées au scanner.

    Le scanner vérifie uniquement `node.module` (le package source d'un import),
    jamais les symboles importés. Avoir `UTC` dans allowed_imports est donc inutile
    mais inoffensif après ce filtrage.
    """
    exact: set[str] = set()
    prefixes: list[str] = []
    skipped: list[str] = []

    for entry in raw_list:
        entry = entry.strip()
        if not entry:
            continue

        if entry.endswith(".*"):
            prefix = entry[:-2]
            if _looks_like_module(prefix):
                prefixes.append(prefix)
                # "sqlalchemy" couvre aussi "import sqlalchemy"
                exact.add(prefix)
            else:
                skipped.append(entry)
        elif _looks_like_module(entry):
            exact.add(entry)
        else:
            # Symbole / classe → ignoré (ex: UTC, UUID, Mapped, TokenVerifyRequest)
            skipped.append(entry)

    return exact, prefixes, skipped


# ─────────────────────────────────────────────────────────────
# ASTScanner — orchestration Python + C++
# ─────────────────────────────────────────────────────────────


class ASTScanner:
    """
    Scanner de plugins xcore.

    - Utilise l'extension C++ (scanner_core) si disponible → multithread,
      extraction regex ultra-rapide, sets O(1).
    - Fallback Python pur si le .so n'est pas compilé.
    - Builtin/attribute checks toujours en Python (nécessitent l'AST complet).
    """

    def __init__(
        self,
        extra_forbidden: set[str] | None = None,
        extra_allowed: set[str] | None = None,
    ):
        forbidden_set = DEFAULT_FORBIDDEN | (extra_forbidden or set())
        allowed_raw = DEFAULT_ALLOWED | (extra_allowed or set())

        # Sépare exact vs wildcards une seule fois à la construction
        self._allowed_exact: set[str] = {
            p for p in allowed_raw if not p.endswith(".*")}
        self._allowed_prefixes: list[str] = [
            p[:-2] for p in allowed_raw if p.endswith(".*")
        ]
        self._forbidden: set[str] = forbidden_set

        # Construit le classificateur C++ si disponible
        if _CPP_AVAILABLE:
            self._cpp = _CppClassifier(
                forbidden=self._forbidden,
                allowed_exact=self._allowed_exact,
                allowed_prefixes=self._allowed_prefixes,
            )
        else:
            self._cpp = None

    # ── Public ───────────────────────────────────────────────

    def scan(
        self,
        plugin_dir: Path,
        whitelist: list[str] | None = None,
        entry_point: str = "src/main.py",
        manifest_allowed_imports: list[str] | None = None,
    ) -> ScanResult:
        """
        Scanne le plugin.

        Parameters
        ----------
        plugin_dir               : répertoire racine du plugin
        whitelist                : modules supplémentaires autorisés (strings brutes)
        entry_point              : chemin relatif de l'entry point
        manifest_allowed_imports : liste brute depuis le manifeste YAML
                                   (peut contenir des symboles, ils seront filtrés)
        """
        result = ScanResult()
        plugin_dir = plugin_dir.resolve()
        entry_path = (plugin_dir / entry_point).resolve()

        if not entry_path.is_relative_to(plugin_dir):
            result.add_error(
                f"Entry point hors du dossier plugin : {entry_point!r}")
            return result
        if not entry_path.exists():
            result.add_error(f"Entry point introuvable : {entry_point!r}")
            return result

        src_dir = entry_path.parent

        # Modules locaux détectés automatiquement depuis src/
        local_modules = _collect_local_modules(src_dir)

        # Construction du scanner effectif avec tous les allowed cumulés
        extra_exact: set[str] = set(whitelist or [])
        if manifest_allowed_imports:
            m_exact, m_prefixes, skipped = _parse_allowed_imports(
                manifest_allowed_imports
            )
            if skipped:
                result.add_warning(
                    f"allowed_imports : {len(skipped)} entrée(s) ignorée(s) car ce sont "
                    f"des symboles/classes, pas des modules : {skipped}"
                )
            extra_exact |= m_exact
            # Reconstruit le scanner avec les préfixes du manifeste intégrés
            scanner = ASTScanner(
                extra_forbidden=set(),
                extra_allowed=extra_exact | {f"{p}.*" for p in m_prefixes},
            )
        else:
            scanner = self if not extra_exact else ASTScanner(
                extra_allowed=extra_exact)

        py_files = sorted(set(src_dir.rglob("*.py")) | {entry_path})
        if not py_files:
            result.add_warning(f"Aucun fichier .py trouvé dans {src_dir}")
            return result

        # ── Scan des imports (C++ ou Python) ─────────────────
        if scanner._cpp is not None:
            cpp_results = scanner._cpp.scan_directory(
                str(src_dir), local_modules)
            for fr in cpp_results:
                for e in fr.errors:
                    result.add_error(e)
                for w in fr.warnings:
                    result.add_warning(w)
        else:
            for py_file in py_files:
                scanner._scan_imports_python(py_file, result, local_modules)

        # ── Vérification builtins/attributs (Python AST) ─────
        for py_file in py_files:
            _check_builtins_and_attrs(py_file, result, scanner._forbidden)
            result.scanned.append(str(py_file.relative_to(plugin_dir)))

        return result

    # ── Fallback Python ──────────────────────────────────────

    def _scan_imports_python(
        self,
        path: Path,
        result: ScanResult,
        local_modules: set[str],
    ) -> None:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            result.add_error(f"{path}: erreur de syntaxe : {e}")
            return
        except Exception as e:
            result.add_error(f"{path}: lecture impossible : {e}")
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_py(alias.name, node.lineno,
                                   path, result, local_modules)

            elif isinstance(node, ast.ImportFrom):
                # Seul node.module est le module source.
                # Les alias.name sont des symboles — on ne les vérifie PAS.
                if node.level and node.level > 0:
                    continue  # import relatif → local
                if node.module:
                    self._check_py(
                        node.module, node.lineno, path, result, local_modules
                    )

    def _check_py(
        self,
        module: str,
        lineno: int,
        path: Path,
        result: ScanResult,
        local_modules: set[str],
    ) -> None:
        root = module.split(".")[0]
        if root in local_modules or module in local_modules:
            return
        loc = f"{path}:{lineno}: "
        if root in self._forbidden:
            result.add_error(loc + f"import interdit — '{module}'")
        elif not self._is_allowed(module):
            result.add_warning(loc + f"import non whitelisté — '{module}'")

    def _is_allowed(self, module: str) -> bool:
        if module in self._allowed_exact:
            return True
        root = module.split(".")[0]
        if root in self._allowed_exact:
            return True
        for prefix in self._allowed_prefixes:
            if module == prefix:
                return True
            if module.startswith(prefix + "."):
                return True
        return False


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _collect_local_modules(src_dir: Path) -> set[str]:
    """
    Construit le set des modules locaux dans src/.

    Pour src/utils/helpers.py on enregistre "utils" ET "utils.helpers",
    couvrant `import utils`, `from utils import helpers`,
    `from utils.helpers import foo`.
    """
    local: set[str] = set()
    for py_file in src_dir.rglob("*.py"):
        rel = py_file.relative_to(src_dir).with_suffix("")
        parts = rel.parts
        for i in range(1, len(parts) + 1):
            local.add(".".join(parts[:i]))
    return local


def _check_builtins_and_attrs(
    path: Path, result: ScanResult, forbidden: set[str]
) -> None:
    """Vérifie les builtins dangereux et attributs interdits (nécessite l'AST)."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        return  # déjà signalé par la phase import

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_BUILTINS:
                result.add_error(
                    f"{path}:{node.lineno}: built-in interdit : {node.id!r}"
                )
            elif node.id in forbidden:
                result.add_error(
                    f"{path}:{node.lineno}: nom interdit : {node.id!r}")

        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRIBUTES:
                result.add_error(
                    f"{path}:{node.lineno}: attribut sensible interdit : {node.attr!r}"
                )
            elif node.attr in forbidden:
                result.add_error(
                    f"{path}:{node.lineno}: attribut de module interdit : {node.attr!r}"
                )
