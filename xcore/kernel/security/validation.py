"""
validation.py — Validation des manifestes et scan AST des plugins.
Regroupe ManifestValidator (nouveau) + ASTScanner (repris de sandbox/sandbox/scanner.py v1).
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

from xcore.sdk.plugin_base import PluginDependency

from .section import (
    DEFAULT_ALLOWED,
    DEFAULT_FORBIDDEN,
    FORBIDDEN_ATTRIBUTES,
    FORBIDDEN_BUILTINS,
    ScanResult,
    _SimpleManifest,
)

# ─────────────────────────────────────────────────────────────
# Manifest
# ─────────────────────────────────────────────────────────────


class ManifestError(Exception):
    pass


_ENV_VAR_RE = re.compile(r"^\$\{(.+)\}$")


def _resolve_env(value: str) -> str:
    # TODO: update env suporte ask, generate, eg: {var:?} {var:-} {var:generate.len(64)}
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
        """Retourne un PluginManifest ou lève ManifestError."""
        from xcore import __version__

        from ..api.contract import ExecutionMode  # import local pour éviter cycle
        from ..api.versioning import check_compatibility

        plugin_dir = Path(plugin_dir).resolve()
        raw = self._read_raw(plugin_dir)

        for field_name in ("name", "version"):
            if not raw.get(field_name):
                raise ManifestError(f"Champ obligatoire manquant : '{field_name}'")

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

        # Injection dotenv si demandé
        self._inject_dotenv(raw.get("envconfiguration"), plugin_dir)

        # Résolution des ${VAR}
        resolved_env = {k: _resolve_env(v) for k, v in raw.get("env", {}).items()}

        # Parse des dépendances avec version
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
        """FIX #4 v1 : gestion correction du bloc envconfiguration."""
        if not cfg or not cfg.get("inject", False):
            return
        env_file = cfg.get("env_file", ".env")
        env_path = (plugin_dir / env_file).resolve()

        # Sécurité : vérifie que le fichier .env est bien dans le dossier du plugin
        if not env_path.is_relative_to(plugin_dir.resolve()):
            raise ManifestError(f"Tentative de traversal via env_file : {env_file!r}")

        if not env_path.exists():
            raise ManifestError(
                f"envconfiguration.inject=true mais '{env_path}' introuvable."
            )
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=env_path, override=False)
        except ImportError as e:
            raise ManifestError("python-dotenv non installé") from e


def _build_manifest(
    raw: dict, mode, resolved_env: dict, requires: list, plugin_dir: Path
):
    """Construit un objet PluginManifest minimal depuis les données brutes."""
    # Import local pour éviter la circularité
    try:
        from ...sdk.plugin_base import PluginManifest
    except ImportError:
        return _SimpleManifest(raw, mode, resolved_env, requires, plugin_dir)
    return PluginManifest.from_raw(raw, mode, resolved_env, requires, plugin_dir)


# ─────────────────────────────────────────────────────────────
# AST Scanner (repris de sandbox/sandbox/scanner.py v1)
# ─────────────────────────────────────────────────────────────


class ASTScanner:
    def __init__(
        self, extra_forbidden: set | None = None, extra_allowed: set | None = None
    ):
        self.forbidden = DEFAULT_FORBIDDEN | (extra_forbidden or set())
        self.allowed = DEFAULT_ALLOWED | (extra_allowed or set())

    def scan(self, plugin_dir: Path, whitelist: list[str] | None = None) -> ScanResult:
        result = ScanResult()
        src_dir = plugin_dir / "src"
        extra_ok = set(whitelist or [])

        if not src_dir.exists():
            result.add_error(f"Répertoire src/ introuvable dans {plugin_dir}")
            return result

        py_files = list(src_dir.rglob("*.py"))
        if not py_files:
            result.add_warning("Aucun fichier .py dans src/")
            return result

        for py_file in py_files:
            self._scan_file(py_file, result, extra_ok)
            result.scanned.append(str(py_file.relative_to(plugin_dir)))

        return result

    def _scan_file(self, path: Path, result: ScanResult, extra_allowed: set) -> None:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            result.add_error(f"{path.name}: syntaxe : {e}")
            return
        except Exception as e:
            result.add_error(f"{path.name}: lecture : {e}")
            return

        visitor = _SecurityVisitor(
            forbidden=self.forbidden,
            allowed=self.allowed | extra_allowed,
            filename=path.name,
            path=path,
        )
        visitor.visit(tree)
        for e in visitor.errors:
            result.add_error(e)
        if visitor.errors:
            result.passed = False
        for w in visitor.warnings:
            result.add_warning(w)


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, forbidden, allowed, filename, path):
        self.forbidden = forbidden
        self.allowed = allowed
        self.filename = filename
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.path: Path = path

    def _check(self, module: str, lineno: int) -> None:
        root = module.split(".")[0]
        if root in self.forbidden:
            self.errors.append(f"{self.path}:{lineno}: import interdit : {module!r}")
        elif root not in self.allowed:
            self.warnings.append(
                f"{self.path}:{lineno}: import non whitelisté : {module!r}"
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._check(node.module, node.lineno)

    def visit_Call(self, node: ast.Call) -> None:
        # __import__ est déjà capturé par visit_Name car il est dans FORBIDDEN_BUILTINS
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_BUILTINS:
            self.errors.append(
                f"{self.path}:{node.lineno}: utilisation de built-in interdit : {node.id!r}"
            )
        elif node.id in self.forbidden:
            self.errors.append(
                f"{self.path}:{node.lineno}: utilisation de nom interdit : {node.id!r}"
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_ATTRIBUTES:
            self.errors.append(
                f"{self.path}:{node.lineno}: accès à l'attribut sensible interdit : {node.attr!r}"
            )
        self.generic_visit(node)
