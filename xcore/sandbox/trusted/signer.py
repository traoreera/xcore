"""
trusted/signer.py
──────────────────
Signature et vérification des plugins Trusted via HMAC-SHA256.

Fonctionnement :
- À la signature   : hash de tous les fichiers src/ + manifest → stocké dans plugin.sig
- À la vérification: recalcul du hash → comparaison avec plugin.sig
- La clé secrète est gérée par le Plugin Manager (jamais dans le plugin)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path

from ..contracts.plugin_manifest import PluginManifest

logger = logging.getLogger("plManager.signer")

SIG_FILENAME = "plugin.sig"


# ──────────────────────────────────────────────
# Erreurs
# ──────────────────────────────────────────────


class SignatureError(Exception):
    """Signature absente, invalide ou modifiée."""


# ──────────────────────────────────────────────
# Calcul du hash du plugin
# ──────────────────────────────────────────────


def _compute_plugin_hash(manifest: PluginManifest, secret_key: bytes) -> str:
    """
    Calcule un HMAC-SHA256 sur le contenu de tous les fichiers src/ + manifest.
    Les fichiers sont triés pour garantir un hash déterministe.
    """
    h = hmac.new(secret_key, digestmod=hashlib.sha256)

    src_dir = manifest.plugin_dir / "src"
    if not src_dir.exists():
        raise SignatureError(f"Répertoire src/ introuvable dans {manifest.plugin_dir}")

    # Hash du manifest lui-même
    manifest_file = manifest.plugin_dir / "plugin.yaml"
    if not manifest_file.exists():
        manifest_file = manifest.plugin_dir / "plugin.json"
    h.update(manifest_file.read_bytes())

    # Hash de tous les fichiers src/ dans l'ordre alphabétique
    for py_file in sorted(src_dir.rglob("*")):
        if py_file.is_file():
            h.update(py_file.name.encode())  # nom du fichier dans le hash
            h.update(py_file.read_bytes())

    return h.hexdigest()


# ──────────────────────────────────────────────
# API publique
# ──────────────────────────────────────────────


def sign_plugin(manifest: PluginManifest, secret_key: bytes) -> Path:
    """
    Signe le plugin et écrit la signature dans plugin.sig.
    Retourne le chemin du fichier de signature.

    À appeler par un outil CLI d'administration, pas au runtime.
    """
    digest = _compute_plugin_hash(manifest, secret_key)
    sig_path = manifest.plugin_dir / SIG_FILENAME

    sig_data = {
        "plugin": manifest.name,
        "version": manifest.version,
        "digest": digest,
    }
    sig_path.write_text(json.dumps(sig_data, indent=2))
    logger.info(f"[{manifest.name}] Signature écrite dans {sig_path}")
    return sig_path


def verify_plugin(manifest: PluginManifest, secret_key: bytes) -> None:
    """
    Vérifie la signature du plugin.
    Lève SignatureError si la signature est absente, invalide ou ne correspond pas.
    """
    sig_path = manifest.plugin_dir / SIG_FILENAME

    if not sig_path.exists():
        raise SignatureError(
            f"[{manifest.name}] Fichier de signature manquant ({SIG_FILENAME}). "
            "Le plugin doit être signé avant d'être activé en mode Trusted."
        )

    try:
        sig_data = json.loads(sig_path.read_text())
    except Exception as e:
        raise SignatureError(f"[{manifest.name}] Fichier .sig illisible : {e}")

    stored_digest = sig_data.get("digest", "")
    if not stored_digest:
        raise SignatureError(f"[{manifest.name}] Champ 'digest' manquant dans .sig")

    # Vérification version
    if sig_data.get("version") != manifest.version:
        raise SignatureError(
            f"[{manifest.name}] Version du manifest ({manifest.version}) "
            f"ne correspond pas à la version signée ({sig_data.get('version')}). "
            "Resignez le plugin après chaque mise à jour."
        )

    expected = _compute_plugin_hash(manifest, secret_key)

    # Comparaison en temps constant (protection timing attack)
    if not hmac.compare_digest(expected, stored_digest):
        raise SignatureError(
            f"[{manifest.name}] ❌ Signature invalide — "
            "le contenu du plugin a été modifié depuis la dernière signature."
        )

    logger.info(f"[{manifest.name}] ✅ Signature vérifiée")


def is_signed(manifest: PluginManifest) -> bool:
    """Retourne True si le plugin possède un fichier .sig."""
    return (manifest.plugin_dir / SIG_FILENAME).exists()
