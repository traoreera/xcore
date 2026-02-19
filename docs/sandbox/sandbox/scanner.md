# scanner.py

Le fichier `xcore/sandbox/sandbox/scanner.py` fait un scan AST statique de sécurité pour les plugins sandboxed.

## Contrôles

- imports interdits (`os`, `subprocess`, `socket`, etc.)
- imports hors whitelist (warning)
- patterns dangereux (`eval`, `exec`, `open`, `__import__`, ...)

## API

- `ASTScanner.scan_plugin(plugin_dir, whitelist=None)`
- `ScanResult` (`passed`, `errors`, `warnings`, `scanned`)

## Exemple

```python
scanner = ASTScanner()
result = scanner.scan_plugin(Path("plugins/demo"), whitelist=["pydantic"])
if not result.passed:
    print(result)
```

## Contribution

- Ajouter des règles avec prudence pour éviter les faux positifs excessifs.
- Chaque nouvelle règle doit être accompagnée d’un test.
