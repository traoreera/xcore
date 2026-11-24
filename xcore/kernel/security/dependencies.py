"""
dependencies.py — Les dépendances d'un plugin : déclarées, et vérifiées (#313).

Un plugin importait `cryptography` sans le nommer nulle part ; c'est l'application en
aval qui l'a découvert, par un `ImportError` chez un client. Rien dans la chaîne ne le
disait : ni l'installation, ni le chargement, ni la CI.

Ce module compare les imports d'un plugin à ce qu'il déclare, et liste les manquants.

  * **Imports** — parcours d'AST de tous les `.py` du plugin (y compris les imports
    paresseux dans une fonction : ils cassent aussi chez le client, seulement plus tard).
    Sont ignorés : la bibliothèque standard, les modules du plugin lui-même, les imports
    relatifs, les blocs `if TYPE_CHECKING:` et les imports gardés par un
    `try/except ImportError` (dépendance optionnelle assumée).
  * **Déclarations** — `pyproject.toml` du plugin (`[project]` et `[tool.poetry]`,
    extras compris), `requirements.txt`, et la clé `dependencies:` du manifeste.
  * **Fournis par l'hôte** — xcore et la fermeture de ses dépendances de noyau
    (fastapi, pydantic, pyyaml…) : un plugin n'a pas à les redéclarer. Les extras
    d'xcore (sqlalchemy, redis, celery…) ne sont PAS fournis : qui les importe les déclare.

Usage :

    from xcore.kernel.security.dependencies import check_plugin_dependencies
    report = check_plugin_dependencies("plugins/erp_mail")
    if not report.ok:
        print(report.render())

    # En CI, chez l'auteur du plugin (code de sortie 1 si une dépendance manque) :
    python -m xcore.kernel.security.dependencies plugins/erp_mail
    xcore-plugin-check plugins/*
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Ce que `pip install XCoreRuntime` (sans extra) apporte : voir [project].dependencies.
CORE_REQUIREMENTS = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "pyyaml",
    "apscheduler",
    "opentelemetry-sdk",
)

# Dossiers d'un plugin qui ne sont pas son code livré.
_SKIPPED_DIRS = frozenset(
    {
        "venv",
        ".venv",
        "sandbox",
        "data",
        "node_modules",
        "__pycache__",
        "tests",
        "test",
        "build",
        "dist",
    }
)

_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXTRA_MARKER_RE = re.compile(r"\bextra\s*==")
_IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def normalize(name: str) -> str:
    """Nom de distribution normalisé (PEP 503) : `Py_YAML` → `py-yaml`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str | None:
    """`cryptography>=42 ; python_version<'4'` → `cryptography` (None si illisible)."""
    match = _REQ_NAME_RE.match(requirement)
    return normalize(match.group(1)) if match else None


# ── Ce que l'environnement fournit ───────────────────────────────────────────


@lru_cache(maxsize=1)
def _module_distributions() -> dict[str, tuple[str, ...]]:
    """Module de haut niveau → distributions installées qui le fournissent."""
    from importlib import metadata

    return {
        module: tuple(sorted({normalize(d) for d in dists}))
        for module, dists in metadata.packages_distributions().items()
    }


@lru_cache(maxsize=1)
def host_provided() -> frozenset[str]:
    """Distributions que l'hôte xcore apporte : xcore + la fermeture de son noyau."""
    from importlib import metadata

    seen: set[str] = set()
    todo = [normalize(name) for name in CORE_REQUIREMENTS]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            requirements = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue
        for requirement in requirements:
            if _EXTRA_MARKER_RE.search(requirement):
                continue  # dépendance d'un extra : pas installée par défaut
            if dep := requirement_name(requirement):
                todo.append(dep)
    return frozenset(seen | {"xcoreruntime", "xcore"})


# ── Ce que le plugin déclare ─────────────────────────────────────────────────


def _pyproject_names(path: Path) -> set[str]:
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    project = data.get("project") or {}
    requirements = list(project.get("dependencies") or [])
    for extra in (project.get("optional-dependencies") or {}).values():
        requirements.extend(extra or [])
    names.update(filter(None, map(requirement_name, requirements)))

    poetry = (data.get("tool") or {}).get("poetry") or {}
    tables = [poetry.get("dependencies") or {}]
    tables += [
        group.get("dependencies") or {}
        for name, group in (poetry.get("group") or {}).items()
        if name not in ("dev", "test", "docs")
    ]
    for table in tables:
        names.update(normalize(key) for key in table if key.lower() != "python")
    return names


def _requirements_txt_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if name := requirement_name(line):
            names.add(name)
    return names


def _manifest_names(plugin_dir: Path) -> set[str] | None:
    """Clé `dependencies:` du manifeste — None si le manifeste n'en a pas."""
    raw: dict | None = None
    if (path := plugin_dir / "plugin.yaml").exists():
        from .. import yamlio

        with open(path, encoding="utf-8") as fh:
            raw = yamlio.safe_load(fh) or {}
    elif (path := plugin_dir / "plugin.json").exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "dependencies" not in raw:
        return None
    declared = raw.get("dependencies") or []
    if not isinstance(declared, list):
        raise ValueError("'dependencies' du manifeste doit être une liste")
    return {name for name in map(requirement_name, map(str, declared)) if name}


def declared_dependencies(plugin_dir: Path) -> tuple[set[str], list[str]]:
    """`(distributions déclarées, fichiers où elles le sont)` pour un plugin."""
    declared: set[str] = set()
    sources: list[str] = []
    if (path := plugin_dir / "pyproject.toml").exists():
        declared |= _pyproject_names(path)
        sources.append("pyproject.toml")
    if (path := plugin_dir / "requirements.txt").exists():
        declared |= _requirements_txt_names(path)
        sources.append("requirements.txt")
    manifest = _manifest_names(plugin_dir)
    if manifest is not None:
        declared |= manifest
        sources.append(
            "plugin.yaml" if (plugin_dir / "plugin.yaml").exists() else "plugin.json"
        )
    return declared, sources


# ── Ce que le plugin importe ─────────────────────────────────────────────────


class _ImportCollector(ast.NodeVisitor):
    """Imports absolus d'un fichier : `module de haut niveau → [numéros de ligne]`."""

    def __init__(self) -> None:
        self.found: dict[str, list[int]] = {}

    def _add(self, module: str, lineno: int) -> None:
        self.found.setdefault(module.split(".", 1)[0], []).append(lineno)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self._add(node.module, node.lineno)

    def visit_If(self, node: ast.If) -> None:
        test = node.test
        name = getattr(test, "id", None) or getattr(test, "attr", None)
        if name == "TYPE_CHECKING":
            for child in node.orelse:  # le corps n'existe pas à l'exécution
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        guarded = any(self._catches_import_error(h) for h in node.handlers)
        if not guarded:
            for child in node.body:
                self.visit(child)
        # Le repli (handlers, else, finally) s'exécute, lui, sans filet.
        for child in [*node.handlers, *node.orelse, *node.finalbody]:
            self.visit(child)

    visit_TryStar = visit_Try

    @staticmethod
    def _catches_import_error(handler: ast.ExceptHandler) -> bool:
        if handler.type is None:
            return True
        types = (
            handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        )
        return any(
            (getattr(t, "id", None) or getattr(t, "attr", None)) in _IMPORT_ERRORS
            for t in types
        )


def _python_files(plugin_dir: Path) -> list[Path]:
    files = []
    for path in sorted(plugin_dir.rglob("*.py")):
        parts = path.relative_to(plugin_dir).parts[:-1]
        if any(part in _SKIPPED_DIRS or part.startswith(".") for part in parts):
            continue
        files.append(path)
    return files


def _local_modules(plugin_dir: Path, files: list[Path]) -> set[str]:
    """Noms importables depuis le plugin lui-même (racine et `src/`)."""
    local = set()
    for root in (plugin_dir, plugin_dir / "src"):
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if entry.suffix == ".py":
                local.add(entry.stem)
            elif entry.is_dir() and any(f.is_relative_to(entry) for f in files):
                local.add(entry.name)
    return local


def collect_imports(plugin_dir: Path) -> tuple[dict[str, list[str]], list[str]]:
    """`(module → ["src/main.py:3", …], fichiers illisibles)` pour tout le plugin."""
    imports: dict[str, list[str]] = {}
    unreadable: list[str] = []
    for path in _python_files(plugin_dir):
        rel = path.relative_to(plugin_dir).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            unreadable.append(rel)
            continue
        collector = _ImportCollector()
        collector.visit(tree)
        for module, lines in collector.found.items():
            imports.setdefault(module, []).extend(f"{rel}:{n}" for n in lines)
    return imports, unreadable


# ── Le contrôle ──────────────────────────────────────────────────────────────


@dataclass
class DependencyReport:
    """Résultat du contrôle d'un plugin."""

    plugin: str
    declared: set[str] = field(default_factory=set)
    sources: list[str] = field(default_factory=list)
    # module importé → où ; pour chaque module non couvert par une déclaration.
    missing: dict[str, list[str]] = field(default_factory=dict)
    # module importé → distribution(s) à déclarer, quand l'environnement le sait.
    suggestions: dict[str, list[str]] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing

    def to_dict(self) -> dict:
        return {
            "plugin": self.plugin,
            "ok": self.ok,
            "declared": sorted(self.declared),
            "sources": self.sources,
            "missing": {m: self.missing[m] for m in sorted(self.missing)},
            "suggestions": {m: self.suggestions[m] for m in sorted(self.suggestions)},
            "unreadable": self.unreadable,
        }

    def render(self) -> str:
        where = (
            ", ".join(self.sources) if self.sources else "aucune déclaration trouvée"
        )
        if self.ok:
            return f"{self.plugin}: ok ({len(self.declared)} dépendance(s) déclarée(s) — {where})"
        lines = [
            f"{self.plugin}: {len(self.missing)} dépendance(s) importée(s) mais non "
            f"déclarée(s) ({where})"
        ]
        for module in sorted(self.missing):
            hint = self.suggestions.get(module)
            name = f"{module} (déclarer : {' ou '.join(hint)})" if hint else module
            lines.append(f"  - {name} — {', '.join(self.missing[module][:3])}")
        return "\n".join(lines)


def check_plugin_dependencies(
    plugin_dir: str | Path, provided: frozenset[str] | set[str] | None = None
) -> DependencyReport:
    """
    Compare les imports d'un plugin à ses dépendances déclarées.

    `provided` : distributions que l'hôte apporte (défaut : xcore et son noyau).
    """
    plugin_dir = Path(plugin_dir).resolve()
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"Plugin folder not found: {plugin_dir}")
    provided = host_provided() if provided is None else {normalize(p) for p in provided}

    declared, sources = declared_dependencies(plugin_dir)
    imports, unreadable = collect_imports(plugin_dir)
    local = _local_modules(plugin_dir, _python_files(plugin_dir))
    distributions = _module_distributions()
    report = DependencyReport(
        plugin=plugin_dir.name,
        declared=declared,
        sources=sources,
        unreadable=unreadable,
    )

    for module, places in imports.items():
        if module in sys.stdlib_module_names or module in local:
            continue
        if module == "xcore" or module.startswith("xcore_plugin_"):
            continue
        candidates = distributions.get(module)
        if candidates is None:
            # Pas installé ici : on ne peut que comparer les noms.
            if normalize(module) in declared | provided:
                continue
            report.missing[module] = places
        elif not set(candidates) & (declared | provided):
            report.missing[module] = places
            report.suggestions[module] = list(candidates)
    return report


# ── Ligne de commande ────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """`xcore-plugin-check <dossier de plugin>…` — 0 si tout est déclaré, 1 sinon."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="xcore-plugin-check",
        description="Compare les imports d'un plugin xcore à ses dépendances déclarées.",
    )
    parser.add_argument("plugins", nargs="+", type=Path, help="dossier(s) de plugin")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    parser.add_argument(
        "--provided",
        action="append",
        default=[],
        metavar="DIST",
        help="distribution fournie par l'hôte, en plus du noyau xcore (répétable)",
    )
    args = parser.parse_args(argv)

    provided = host_provided() | {normalize(p) for p in args.provided}
    reports, status = [], 0
    for plugin_dir in args.plugins:
        try:
            report = check_plugin_dependencies(plugin_dir, provided)
        except (FileNotFoundError, ValueError) as exc:
            print(f"{plugin_dir}: {exc}", file=sys.stderr)
            status = 2
            continue
        reports.append(report)
        if not report.ok and status == 0:
            status = 1
    if args.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False))
    else:
        for report in reports:
            print(report.render())
    return status


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
