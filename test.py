"""
sign_plugin.py
───────────────
Script CLI de signature d'un plugin avant déploiement.
À exécuter UNE FOIS par l'administrateur après chaque modification du plugin.

Usage :
    python sign_plugin.py --plugin ./weather_cache --key "ma-cle-secrete"
    python sign_plugin.py --plugin ./weather_cache --key-env PLUGIN_SECRET_KEY
    python sign_plugin.py --plugin ./weather_cache --verify   # vérification seule
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path


# ══════════════════════════════════════════════
# Reproduction locale de signer.py
# (pour pouvoir utiliser ce script standalone)
# ══════════════════════════════════════════════

SIG_FILENAME = "plugin.sig"


def _compute_hash(plugin_dir: Path, secret_key: bytes) -> str:
    h = hmac.new(secret_key, digestmod=hashlib.sha256)

    src_dir = plugin_dir / "src"
    if not src_dir.exists():
        raise FileNotFoundError(f"src/ introuvable dans {plugin_dir}")

    # Hash du manifest
    for name in ("plugin.yaml", "plugin.json"):
        manifest_file = plugin_dir / name
        if manifest_file.exists():
            h.update(manifest_file.read_bytes())
            break
    else:
        raise FileNotFoundError("plugin.yaml ou plugin.json introuvable")

    # Hash de tous les fichiers src/ triés alphabétiquement
    for py_file in sorted(src_dir.rglob("*")):
        if py_file.is_file():
            h.update(py_file.name.encode())
            h.update(py_file.read_bytes())
            print(f"   hashed: {py_file.relative_to(plugin_dir)}")

    return h.hexdigest()


def _read_manifest_meta(plugin_dir: Path) -> dict:
    for name in ("plugin.yaml", "plugin.json"):
        p = plugin_dir / name
        if p.exists():
            if name.endswith(".yaml"):
                try:
                    import yaml
                    return yaml.safe_load(p.read_text()) or {}
                except ImportError:
                    pass
            else:
                return json.loads(p.read_text())
    return {}


def sign(plugin_dir: Path, secret_key: bytes) -> Path:
    meta   = _read_manifest_meta(plugin_dir)
    name   = meta.get("name", plugin_dir.name)
    version = meta.get("version", "unknown")
    mode   = meta.get("execution_mode", "unknown")

    print(f"\n🔑 Signature du plugin : {name} v{version} [{mode}]")
    print(f"   Répertoire : {plugin_dir}")
    print(f"   Fichiers inclus dans le hash :")

    digest   = _compute_hash(plugin_dir, secret_key)
    sig_path = plugin_dir / SIG_FILENAME

    sig_data = {
        "plugin":  name,
        "version": version,
        "mode":    mode,
        "digest":  digest,
    }
    sig_path.write_text(json.dumps(sig_data, indent=2))

    print(f"\n✅ Signature générée : {sig_path}")
    print(f"   digest  : {digest[:16]}...{digest[-8:]}")
    print(f"   version : {version}")
    return sig_path


def verify(plugin_dir: Path, secret_key: bytes) -> bool:
    meta    = _read_manifest_meta(plugin_dir)
    name    = meta.get("name", plugin_dir.name)
    version = meta.get("version", "unknown")

    print(f"\n🔍 Vérification de : {name} v{version}")

    sig_path = plugin_dir / SIG_FILENAME
    if not sig_path.exists():
        print(f"❌ Fichier {SIG_FILENAME} absent — plugin non signé")
        return False

    sig_data       = json.loads(sig_path.read_text())
    stored_digest  = sig_data.get("digest", "")
    signed_version = sig_data.get("version", "")

    if signed_version != version:
        print(
            f"❌ Version mismatch : manifest={version}, "
            f"signature={signed_version}"
        )
        print("   → Resignez le plugin après chaque mise à jour.")
        return False

    expected = _compute_hash(plugin_dir, secret_key)

    if hmac.compare_digest(expected, stored_digest):
        print(f"✅ Signature valide")
        print(f"   digest  : {stored_digest[:16]}...{stored_digest[-8:]}")
        return True
    else:
        print("❌ Signature INVALIDE — contenu modifié après signature")
        print(f"   attendu : {expected[:16]}...{expected[-8:]}")
        print(f"   stocké  : {stored_digest[:16]}...{stored_digest[-8:]}")
        return False


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Signe ou vérifie un plugin plManager"
    )
    parser.add_argument(
        "--plugin", required=True,
        help="Chemin vers le répertoire du plugin"
    )
    parser.add_argument(
        "--key", default=None,
        help="Clé secrète en clair (déconseillé en prod)"
    )
    parser.add_argument(
        "--key-env", default="PLUGIN_SECRET_KEY",
        help="Variable d'environnement contenant la clé (défaut: PLUGIN_SECRET_KEY)"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Vérification seulement, sans signer"
    )
    args = parser.parse_args()

    plugin_dir = Path(args.plugin).resolve()
    if not plugin_dir.exists():
        print(f"❌ Répertoire introuvable : {plugin_dir}")
        sys.exit(1)

    # Résolution de la clé
    if args.key:
        secret_key = args.key.encode()
    else:
        raw = os.environ.get(args.key_env)
        if not raw:
            print(
                f"❌ Clé introuvable. Utilise --key ou "
                f"export {args.key_env}=ta_cle"
            )
            sys.exit(1)
        secret_key = raw.encode()

    if args.verify:
        ok = verify(plugin_dir, secret_key)
        sys.exit(0 if ok else 1)
    else:
        sign(plugin_dir, secret_key)
        print("\n   Vérifie avec :")
        print(f"   python sign_plugin.py --plugin {args.plugin} --verify\n")


if __name__ == "__main__":
    main()