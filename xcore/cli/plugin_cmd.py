"""
plugin_cmd.py — Handlers des commandes `xcore plugin *`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_config(args):
    from xcore.configurations.loader import ConfigLoader
    return ConfigLoader.load(getattr(args, "config", None))


async def handle_plugin(args) -> None:
    sub = getattr(args, "subcommand", None)

    if sub == "list":
        await _plugin_list(args)
    elif sub == "load":
        await _plugin_load(args)
    elif sub == "reload":
        await _plugin_reload(args)
    elif sub == "sign":
        await _plugin_sign(args)
    elif sub == "verify":
        await _plugin_verify(args)
    elif sub == "validate":
        await _plugin_validate(args)
    else:
        print("Usage : xcore plugin <list|load|reload|sign|verify|validate>")


async def _plugin_list(args) -> None:
    from xcore import Xcore
    cfg = _load_config(args)
    app = Xcore.__new__(Xcore)
    app._config = cfg
    app._booted = False
    # Listing statique depuis le dossier
    plugin_dir = Path(cfg.plugins.directory)
    if not plugin_dir.exists():
        print(f"Dossier plugins introuvable : {plugin_dir}")
        return
    plugins = sorted([d.name for d in plugin_dir.iterdir() if d.is_dir() and not d.name.startswith("_")])
    if not plugins:
        print("Aucun plugin trouvé.")
        return
    print(f"Plugins dans {plugin_dir} ({len(plugins)}) :")
    for p in plugins:
        manifest_path = plugin_dir / p / "plugin.yaml"
        if manifest_path.exists():
            try:
                import yaml
                with open(manifest_path) as f:
                    m = yaml.safe_load(f) or {}
                version = m.get("version", "?")
                mode    = m.get("execution_mode", "legacy")
                print(f"  {p:30s}  v{version:10s}  [{mode}]")
            except Exception:
                print(f"  {p}")
        else:
            print(f"  {p}")


async def _plugin_validate(args) -> None:
    from xcore.kernel.security.validation import ManifestValidator
    path = Path(args.path)
    if not path.exists():
        print(f"❌  Dossier introuvable : {path}", file=sys.stderr)
        sys.exit(1)
    try:
        v = ManifestValidator()
        manifest = v.load_and_validate(path)
        print(f"✅  Manifeste valide : {manifest.name} v{manifest.version} [{manifest.execution_mode.value}]")
    except Exception as e:
        print(f"❌  Manifeste invalide : {e}", file=sys.stderr)
        sys.exit(1)


async def _plugin_sign(args) -> None:
    from xcore.kernel.security.signature import sign_plugin
    from xcore.kernel.security.validation import ManifestValidator
    path = Path(args.path)
    key  = (args.key or "change-me").encode()
    manifest = ManifestValidator().load_and_validate(path)
    sig = sign_plugin(manifest, key)
    print(f"✅  Signé : {sig}")


async def _plugin_verify(args) -> None:
    from xcore.kernel.security.signature import verify_plugin, SignatureError
    from xcore.kernel.security.validation import ManifestValidator
    path = Path(args.path)
    key  = (args.key or "change-me").encode()
    manifest = ManifestValidator().load_and_validate(path)
    try:
        verify_plugin(manifest, key)
        print(f"✅  Signature valide : {manifest.name}")
    except SignatureError as e:
        print(f"❌  {e}", file=sys.stderr)
        sys.exit(1)


async def _plugin_load(args) -> None:
    print(f"ℹ️   'xcore plugin load' nécessite un serveur xcore en cours d'exécution.")
    print(f"    Utilisez l'API HTTP POST /app/{args.name}/load")


async def _plugin_reload(args) -> None:
    print(f"ℹ️   'xcore plugin reload' nécessite un serveur xcore en cours d'exécution.")
    print(f"    Utilisez l'API HTTP POST /app/{args.name}/reload")


async def handle_services(args) -> None:
    sub = getattr(args, "subcommand", None)
    if sub == "status":
        cfg = _load_config(args)
        from xcore.services import ServiceContainer
        container = ServiceContainer(cfg.services)
        await container.init()
        status = container.status()
        print(json.dumps(status, indent=2, default=str))
        await container.shutdown()


async def handle_health(args) -> None:
    cfg = _load_config(args)
    from xcore.services import ServiceContainer
    container = ServiceContainer(cfg.services)
    await container.init()
    health = await container.health()
    symbol = "✅" if health["ok"] else "❌"
    print(f"{symbol} Health : {'OK' if health['ok'] else 'DÉGRADÉ'}")
    for svc, info in health["services"].items():
        sym = "✅" if info["ok"] else "❌"
        print(f"  {sym} {svc}: {info['msg']}")
    await container.shutdown()
