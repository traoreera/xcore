from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path

logger = logging.getLogger("xcore.security.signature")
SIG_FILENAME = "plugin.sig"

SECURITY_IGNORE = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
}


class SignatureError(Exception):
    """Signature absente, invalide ou modifiée."""


def _should_ignore(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)

    if any(part in SECURITY_IGNORE for part in rel.parts):
        return True

    if path.suffix in {".pyc", ".pyo"}:
        return True

    if path.is_symlink():
        return True

    return False


def _compute_hmac(manifest, secret_key: bytes) -> str:
    """
    Calcule un HMAC déterministe du plugin.
    """

    root = manifest.plugin_dir.resolve()
    h = hmac.new(secret_key, digestmod=hashlib.sha256)

    # --- Hash du manifeste ---
    for fname in ("plugin.yaml", "plugin.json"):
        p = root / fname
        if p.exists():
            h.update(p.read_bytes())
            break

    # --- Hash des sources ---
    src_dir = root / "src"
    if not src_dir.exists():
        raise SignatureError(f"Répertoire src/ introuvable dans {root}")

    files = sorted(
        p for p in src_dir.rglob("*") if p.is_file() and not _should_ignore(p, root)
    )

    for path in files:
        rel = path.relative_to(root).as_posix()

        # hash chemin relatif (évite collisions)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")

        # hash contenu streaming
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)

        h.update(b"\0")

    return h.hexdigest()


def sign_plugin(manifest, secret_key: bytes) -> Path:
    digest = _compute_hmac(manifest, secret_key)

    sig_path = manifest.plugin_dir / SIG_FILENAME

    sig_data = {
        "plugin": manifest.name,
        "version": manifest.version,
        "digest": digest,
        "algo": "HMAC-SHA256",
    }

    sig_path.write_text(json.dumps(sig_data, indent=2))
    logger.info(f"[{manifest.name}] Signature écrite : {sig_path}")

    return sig_path


def verify_plugin(manifest, secret_key: bytes) -> None:
    sig_path = manifest.plugin_dir / SIG_FILENAME

    if not sig_path.exists():
        raise SignatureError(f"[{manifest.name}] Signature manquante ({SIG_FILENAME}).")

    try:
        sig_data = json.loads(sig_path.read_text())
    except Exception as e:
        raise SignatureError(f"[{manifest.name}] Fichier .sig illisible : {e}") from e

    stored = sig_data.get("digest")
    if not stored:
        raise SignatureError(f"[{manifest.name}] Champ 'digest' manquant.")

    if sig_data.get("version") != manifest.version:
        raise SignatureError(
            f"[{manifest.name}] Version mismatch. "
            f"Signé: {sig_data.get('version')} / Actuel: {manifest.version}"
        )

    expected = _compute_hmac(manifest, secret_key)

    if not hmac.compare_digest(expected, stored):
        raise SignatureError(
            f"[{manifest.name}] ❌ Signature invalide — contenu modifié."
        )

    logger.info(f"[{manifest.name}] ✅ Signature vérifiée")


def is_signed(manifest) -> bool:
    sig_path = manifest.plugin_dir / SIG_FILENAME
    return sig_path.exists()
