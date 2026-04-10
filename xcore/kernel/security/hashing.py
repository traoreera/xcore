from __future__ import annotations

import fnmatch
import hashlib
import hmac
from pathlib import Path

SECURITY_IGNORE = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".DS_Store",
}

SUFFIX_IGNORE = {
    ".pyc",
    ".pyo",
    ".py.class",
}

PATTERNS_IGNORE = [
    "*.log",  # Exemple de motif pour ignorer tous les fichiers .log
    "*.tmp",  # Ignorer tous les fichiers .tmp
    "temp/**/*",  # Ignorer le dossier temp et son contenu
    "*.md",
]


def __should_ignore(path: Path, root: Path) -> bool:
    """Détermine si un fichier ou un dossier doit être ignoré."""

    rel = path.relative_to(root)
    if any(part in SECURITY_IGNORE for part in rel.parts) or path.name.startswith("."):
        return True

    if path.suffix in SUFFIX_IGNORE:
        return True

    if path.is_symlink():
        return True

    # Vérifier les motifs de fichiers à ignorer
    if any(fnmatch.fnmatch(str(path), pattern) for pattern in PATTERNS_IGNORE):
        return True

    return False


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    """Retourne le hash hex d'un fichier."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def hash_dir(directory: Path, algorithm: str = "sha256") -> str:
    """Hash déterministe de tous les fichiers d'un dossier (ordre alphabétique)."""
    h = hashlib.new(algorithm)
    for path in sorted(directory.rglob("*")):
        if __should_ignore(path, directory):
            continue
        if path.is_file():
            h.update(path.name.encode())
            h.update(hash_file(path, algorithm).encode())
    return h.hexdigest()


def hmac_sign(data: bytes, secret: bytes) -> str:
    """HMAC-SHA256 sur des données brutes."""
    return hmac.new(secret, data, hashlib.sha256).hexdigest()


def hmac_verify(data: bytes, secret: bytes, digest: str) -> bool:
    """Vérifie un HMAC-SHA256 en temps constant."""
    expected = hmac_sign(data, secret)
    return hmac.compare_digest(expected, digest)
