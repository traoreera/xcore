"""
validate_cmd.py — Validation complète d'un plugin (manifeste + AST + signature).

Usage:
    xcore plugin validate ./plugins/my_plugin
"""
from __future__ import annotations

import sys
from pathlib import Path


def validate_full(plugin_path: str, secret_key: bytes = b"", strict: bool = False) -> bool:
    """
    Validation complète d'un plugin :
      1. Lecture manifeste
      2. Validation schéma
      3. Scan AST
      4. Vérification signature (si trusted + secret_key fourni)

    Retourne True si tout est valide.
    """
    from xcore.kernel.security.validation import ManifestValidator, ASTScanner
    from xcore.kernel.api.contract import ExecutionMode

    path = Path(plugin_path).resolve()
    ok   = True

    print(f"\n{'='*50}")
    print(f" Validation : {path.name}")
    print(f"{'='*50}")

    # 1. Manifeste
    try:
        validator = ManifestValidator()
        manifest  = validator.load_and_validate(path)
        print(f"✅  Manifeste   : {manifest.name} v{manifest.version} [{manifest.execution_mode.value}]")
    except Exception as e:
        print(f"❌  Manifeste   : {e}", file=sys.stderr)
        return False

    # 2. AST scan
    scanner = ASTScanner()
    result  = scanner.scan(path, whitelist=manifest.allowed_imports)
    if result.passed:
        print(f"✅  Scan AST    : {len(result.scanned)} fichier(s) analysé(s)")
    else:
        print(f"❌  Scan AST    :")
        for err in result.errors:
            print(f"     {err}", file=sys.stderr)
        ok = False
    for w in result.warnings:
        print(f"⚠️   AST warning : {w}")

    # 3. Signature (Trusted seulement)
    if manifest.execution_mode == ExecutionMode.TRUSTED and secret_key:
        from xcore.kernel.security.signature import verify_plugin, SignatureError
        try:
            verify_plugin(manifest, secret_key)
            print(f"✅  Signature   : valide")
        except SignatureError as e:
            if strict:
                print(f"❌  Signature   : {e}", file=sys.stderr)
                ok = False
            else:
                print(f"⚠️   Signature   : {e}")

    print(f"\n{'='*50}")
    print(f" Résultat : {'✅ VALIDE' if ok else '❌ INVALIDE'}")
    print(f"{'='*50}\n")
    return ok
