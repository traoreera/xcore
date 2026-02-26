"""
signature.py — Signature et vérification HMAC-SHA256 des plugins Trusted.
Repris de sandbox/trusted/signer.py v1 avec refactoring propre.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
from pathlib import Path

from .hashing import hmac_verify

logger = logging.getLogger("xcore.security.signature")
SIG_FILENAME = "plugin.sig"


class SignatureError(Exception):
    """Signature absente, invalide ou modifiée."""


def _compute_hash(manifest, secret_key: bytes) -> str:
    h = hmac.new(secret_key, digestmod=hashlib.sha256)

    src_dir = manifest.plugin_dir / "src"
    if not src_dir.exists():
        raise SignatureError(f"Répertoire src/ introuvable dans {manifest.plugin_dir}")

    # Hash du manifeste
    for fname in ("plugin.yaml", "plugin.json"):
        p = manifest.plugin_dir / fname
        if p.exists():
            h.update(p.read_bytes())
            break

    # Hash des sources par ordre alphabétique
    for py_file in sorted(src_dir.rglob("*")):
        if py_file.is_file():
            h.update(py_file.name.encode())
            h.update(py_file.read_bytes())

    return h.hexdigest()


def sign_plugin(manifest, secret_key: bytes) -> Path:
    """Signe le plugin et écrit plugin.sig. À appeler via CLI."""
    digest = _compute_hash(manifest, secret_key)
    sig_path = manifest.plugin_dir / SIG_FILENAME
    sig_data = {"plugin": manifest.name, "version": manifest.version, "digest": digest}
    sig_path.write_text(json.dumps(sig_data, indent=2))
    logger.info(f"[{manifest.name}] Signature écrite : {sig_path}")
    return sig_path


def verify_plugin(manifest, secret_key: bytes) -> None:
    """Vérifie la signature. Lève SignatureError si invalide."""
    sig_path = manifest.plugin_dir / SIG_FILENAME

    if not sig_path.exists():
        raise SignatureError(
            f"[{manifest.name}] Signature manquante ({SIG_FILENAME}). "
            "Signez le plugin avant activation en mode Trusted."
        )

    try:
        sig_data = json.loads(sig_path.read_text())
    except Exception as e:
        raise SignatureError(f"[{manifest.name}] Fichier .sig illisible : {e}") from e

    stored = sig_data.get("digest", "")
    if not stored:
        raise SignatureError(f"[{manifest.name}] Champ 'digest' manquant dans .sig")

    if sig_data.get("version") != manifest.version:
        raise SignatureError(
            f"[{manifest.name}] Version manifest ({manifest.version}) ≠ "
            f"version signée ({sig_data.get('version')}). Resignez le plugin."
        )

    expected = _compute_hash(manifest, secret_key)
    if not hmac.compare_digest(expected, stored):
        raise SignatureError(
            f"[{manifest.name}] ❌ Signature invalide — contenu modifié depuis la signature."
        )

    logger.info(f"[{manifest.name}] ✅ Signature vérifiée")


def is_signed(manifest) -> bool:
    return (manifest.plugin_dir / SIG_FILENAME).exists()
