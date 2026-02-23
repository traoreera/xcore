"""
Scan statique AST des plugins Sandboxed.
Vérifie les imports interdits et patterns dangereux avant tout démarrage.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# Modules interdits par défaut pour les plugins Sandboxed
DEFAULT_FORBIDDEN_MODULES: set[str] = {
    # Accès système dangereux
    "os",
    "path",
    "sys",
    "subprocess",
    "shutil",
    "signal",
    "ctypes",
    "cffi",
    "mmap",
    # Réseau non contrôlé
    "socket",
    "ssl",
    "http",
    "urllib",
    "httpx",
    "requests",
    "aiohttp",
    "websockets",
    # Introspection / code dynamique
    "importlib",
    "imp",
    "builtins",
    "inspect",
    "gc",
    "tracemalloc",
    "dis",
    # Accès fichiers hors data/
    "tempfile",
    "glob",
    # Exécution de code
    "exec",
    "eval",
    "compile",
    "pickle",
    "shelve",
    "marshal",
}

# Modules toujours autorisés même pour Sandboxed
DEFAULT_ALLOWED_MODULES: set[str] = {
    "json",
    "re",
    "math",
    "random",
    "datetime",
    "time",
    "pathlib",
    "typing",
    "dataclasses",
    "enum",
    "functools",
    "itertools",
    "collections",
    "string",
    "hashlib",
    "base64",
    "asyncio",
    "logging",
}

# Patterns de code dangereux (nom de fonction/attribut)
DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b__import__\b"),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bcompile\s*\("),
    re.compile(r"\bopen\s*\("),  # accès fichier direct sans pathlib
    re.compile(r"\bgetattr\s*\(.+,\s*['\"]__"),  # accès dunder via getattr
]


# ──────────────────────────────────────────────
# Résultats
# ──────────────────────────────────────────────


@dataclass
class ScanResult:
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scanned: list[str] = field(default_factory=list)  # fichiers analysés

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def __str__(self) -> str:
        lines = [f"Scan {'✅ PASSED' if self.passed else '❌ FAILED'}"]
        lines += [f"  ❌ {e}" for e in self.errors]
        lines += [f"  ⚠️  {w}" for w in self.warnings]
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Scanner
# ──────────────────────────────────────────────


class ASTScanner:
    """
    Analyse statique des fichiers Python d'un plugin Sandboxed.
    """

    def __init__(
        self,
        extra_forbidden: set[str] | None = None,
        extra_allowed: set[str] | None = None,
    ) -> None:
        self.forbidden = DEFAULT_FORBIDDEN_MODULES | (extra_forbidden or set())
        self.allowed = DEFAULT_ALLOWED_MODULES | (extra_allowed or set())

    # ──────────────────────────────────────────
    # Point d'entrée public
    # ──────────────────────────────────────────

    def scan_plugin(
        self,
        plugin_dir: Path,
        whitelist: list[str] | None = None,
    ) -> ScanResult:
        """
        Scanne tous les fichiers .py dans plugin_dir/src/.
        whitelist : modules supplémentaires autorisés déclarés dans plugin.yaml
        """
        result = ScanResult()
        src_dir = plugin_dir / "src"
        extra_ok = set(whitelist or [])

        if not src_dir.exists():
            result.add_error(f"Répertoire src/ introuvable dans {plugin_dir}")
            return result

        py_files = list(src_dir.rglob("*.py"))
        if not py_files:
            result.add_warning("Aucun fichier .py trouvé dans src/")
            return result

        for py_file in py_files:
            self._scan_file(py_file, result, extra_ok)
            result.scanned.append(str(py_file.relative_to(plugin_dir)))

        return result

    # ──────────────────────────────────────────
    # Analyse d'un fichier
    # ──────────────────────────────────────────

    def _scan_file(
        self,
        path: Path,
        result: ScanResult,
        extra_allowed: set[str],
    ) -> None:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            result.add_error(f"{path.name}: erreur de syntaxe : {e}")
            return
        except Exception as e:
            result.add_error(f"{path.name}: impossible de lire : {e}")
            return

        visitor = _ImportVisitor(
            forbidden=self.forbidden,
            allowed=self.allowed | extra_allowed,
            filename=path.name,
        )
        visitor.visit(tree)
        result.errors.extend(visitor.errors)
        if visitor.errors:
            result.passed = False

        result.warnings.extend(visitor.warnings)

        # Patterns regex sur le source brut
        for pattern in DANGEROUS_PATTERNS:
            for i, line in enumerate(source.splitlines(), 1):
                if pattern.search(line):
                    result.add_error(
                        f"{path.name}:{i}: pattern dangereux détecté : "
                        f"{pattern.pattern!r} → {line.strip()!r}"
                    )


# ──────────────────────────────────────────────
# Visitor AST interne
# ──────────────────────────────────────────────


class _ImportVisitor(ast.NodeVisitor):
    def __init__(
        self,
        forbidden: set[str],
        allowed: set[str],
        filename: str,
    ) -> None:
        self.forbidden = forbidden
        self.allowed = allowed
        self.filename = filename
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def _check_module(self, module: str, lineno: int) -> None:
        root = module.split(".")[0]
        if root in self.forbidden:
            self.errors.append(
                f"{self.filename}:{lineno}: import interdit : {module!r}"
            )
        elif root not in self.allowed:
            self.warnings.append(
                f"{self.filename}:{lineno}: import non whitelisté : {module!r} "
                "(autorisé mais non vérifié)"
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._check_module(node.module, node.lineno)

    def visit_Call(self, node: ast.Call) -> None:
        # Détecte __import__("module")
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            self.errors.append(
                f"{self.filename}:{node.lineno}: __import__() dynamique interdit"
            )
        self.generic_visit(node)
