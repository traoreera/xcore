# Exemple : Plugin en Bac à sable (Sandboxed Plugin)

Le mode `sandboxed` est conçu pour les plugins tiers ou dont vous ne maîtrisez pas le code source. Il garantit une isolation de sécurité maximale.

---

## 1. Caractéristiques du mode Sandboxed

- **Processus Isolé** : S'exécute dans un sous-processus Python distinct.
- **FS Guard** : Accès au système de fichiers restreint (défaut: uniquement `data/`).
- **AST Scan** : Code analysé à la recherche d'imports dangereux (`os`, `sys`, `subprocess`).
- **Ctypes Blocked** : Accès aux bibliothèques C natives (`libc`, `ctypes`) désactivé.
- **Communication IPC** : Échange de données via JSON-RPC uniquement.

---

## 2. Le Manifeste (`plugin.yaml`)

```yaml
name: risky_calculator
version: 1.0.0
author: Third Party Dev
description: Un plugin de calcul qui peut traiter des données locales
execution_mode: sandboxed
entry_point: src/main.py

# Politique de sécurité du système de fichiers
filesystem:
  allowed_paths: ["data/"]      # Seul ce dossier est accessible
  denied_paths: ["src/", "../"] # Blocage explicite des sources et parents

# Limites de ressources matérielles
resources:
  max_memory_mb: 64             # RAM maximale avant crash (64 Mo)
  timeout_seconds: 5            # Temps de réponse maximal par appel (5 s)
```

---

## 3. Le Code Source (`src/main.py`)

```python
import json
from pathlib import Path
from xcore.sdk import TrustedBase, ok, error

class Plugin(TrustedBase):
    """
    Plugin Sandboxed démontrant l'isolation FS.
    """

    async def on_load(self) -> None:
        """Accès sécurisé au dossier data/."""
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        print("✅ Plugin Sandboxed démarré dans son processus isolé.")

    async def handle(self, action: str, payload: dict) -> dict:
        """
        Point d'entrée pour les appels IPC.
        """
        if action == "save_result":
            # Sauvegarde autorisée dans le dossier data/
            result_file = self.data_dir / "last_result.json"
            result_file.write_text(json.dumps(payload))
            return ok(msg="Résultat sauvegardé dans le bac à sable.")

        if action == "read_secrets":
            # TENTATIVE DE VIOLATION : Lecture hors de data/
            try:
                # Tentative d'accès au fichier de config framework (BLOQUÉ par FS Guard)
                with open("../../xcore.yaml", "r") as f:
                    content = f.read()
                return ok(content=content)
            except PermissionError as e:
                # Retourne l'erreur de violation sans crasher le framework
                return error(str(e), code="security_violation")

        if action == "execute_os":
            # TENTATIVE DE VIOLATION : Import de module interdit
            try:
                import os # BLOQUÉ par l'Import Hook
                return ok(msg=f"OS : {os.name}")
            except (PermissionError, ImportError) as e:
                return error(str(e), code="security_violation")

        return ok(status="running")
```

---

## 4. Test de l'Exemple

### Appel d'une action autorisée

```bash
curl -X POST http://localhost:8082/plugin/ipc/risky_calculator/save_result \
  -H "X-Plugin-Key: change-me-in-production" \
  -d '{"payload": {"score": 100}}'

# Réponse :
# {"status":"ok","plugin":"risky_calculator","action":"save_result","result":{"status":"ok","msg":"Résultat sauvegardé..."}}
```

### Appel d'une action bloquée (Tentative de violation)

```bash
curl -X POST http://localhost:8082/plugin/ipc/risky_calculator/read_secrets \
  -H "X-Plugin-Key: change-me-in-production" \
  -d '{"payload": {}}'

# Réponse :
# {"status":"error","plugin":"risky_calculator","action":"read_secrets","result":{"status":"error","msg":"[sandbox] open('../../xcore.yaml') interdit dans le sandbox","code":"security_violation"}}
```

---

## Points Clés de l'Exemple

✅ **Isolation totale** : Les erreurs de sécurité ne propagent pas de crash au Noyau.
✅ **FS Guard** : Blocage dynamique des accès fichiers non autorisés.
✅ **Import Hook** : Blocage des modules système Python critiques.
✅ **Communication IPC** : Le plugin reçoit uniquement les données JSON dont il a besoin.
