# Exemple de Plugin Sandboxé

Cet exemple présente un plugin de traitement d'images sécurisé fonctionnant en mode `sandboxed`. Il illustre l'isolation totale, la liste blanche d'imports et les limites de ressources.

## Cas d'usage : Processeur d'Images

Ce plugin est idéal pour le mode sandbox car il manipule des fichiers binaires externes potentiellement corrompus et utilise des bibliothèques de traitement d'image complexes.

## Structure du Plugin

```text
plugins/image_processor/
├── plugin.yaml
├── src/
│   └── main.py
└── data/                # Seul dossier accessible en écriture
```

## `plugin.yaml`

Le manifeste définit les barrières de sécurité du plugin.

```yaml
name: image_processor
version: 1.0.0
author: XCore Team
description: Traitement d'images sécurisé avec isolation système

execution_mode: sandboxed
framework_version: ">=2.0"
entry_point: src/main.py

# Liste blanche stricte (AST scanner bloquera tout le reste)
allowed_imports:
  - PIL
  - io
  - base64
  - hashlib

# Ressources strictement limitées (OS level via RLIMIT_AS)
resources:
  timeout_seconds: 5
  max_memory_mb: 128
  rate_limit:
    calls: 10
    period_seconds: 60

# Restriction filesystem (Monkey-patching de FilesystemGuard)
filesystem:
  allowed_paths: ["data/"]
  denied_paths: ["src/"]
```

## `src/main.py`

En mode sandbox, le plugin implémente directement le contrat `BasePlugin` sans forcément hériter de `TrustedBase` (qui donne accès à trop de services).

```python
import io
import base64
from PIL import Image
from xcore.sdk import ok, error

class Plugin:
    """Traitement d'image isolé dans un subprocess."""

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "grayscale":
            return await self._grayscale(payload)
        return error(f"Action {action} inconnue ou interdite en sandbox")

    async def _grayscale(self, payload: dict):
        try:
            # 1. Lecture sécurisée (image passée en base64)
            img_data = base64.b64decode(payload["image"])
            img = Image.open(io.BytesIO(img_data))

            # 2. Traitement CPU-bound
            img = img.convert("L")

            # 3. Écriture dans data/ (seul dossier autorisé par le guard)
            # Toute tentative hors data/ lèvera une PermissionError
            img.save("data/last_processed.png")

            # 4. Retour du résultat
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return ok(
                image=base64.b64encode(buffered.getvalue()).decode(),
                size=len(img_data)
            )
        except Exception as e:
            # Les erreurs sont capturées et transmises au canal IPC
            return error(str(e), code="processing_error")

# Marqueur pour le loader xcore
Plugin.__protocol__ = True
```

## Points clés de sécurité démontrés

1.  **Isolation Filesystem** : L'utilisation de `img.save("data/...")` est autorisée. Une tentative comme `img.save("/etc/passwd")` est interceptée par le `FilesystemGuard` et produit un log d'audit critique.
2.  **Sécurité AST** : L' `ASTScanner` analyse le code avant chargement. L'utilisation de `eval()`, `exec()` ou l'accès à `__globals__` est physiquement impossible.
3.  **RLIMIT_AS** : Si l'image est trop grande et que la mémoire dépasse 128 Mo, le processus est immédiatement tué par le noyau Linux, protégeant le reste du framework.
4.  **IPC JSON-RPC** : La communication se fait exclusivement par flux JSON sur `stdin/stdout`, garantissant qu'aucune mémoire n'est partagée.
