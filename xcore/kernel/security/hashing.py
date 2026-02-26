"""
hashing.py — Utilitaires de hachage pour la vérification d'intégrité.
"""
from __future__ import annotations
import hashlib
import hmac
from pathlib import Path


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
