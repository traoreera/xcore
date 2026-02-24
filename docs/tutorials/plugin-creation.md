# Créer un plugin complet sandboxed

Ce tutoriel couvre la création d'un plugin  sandboxe de bout en bout. 

**Prérequis :** avoir suivi l'[introduction](./introduction.md)

---

## Ce que nous allons créer

Un plugin `note` qui expose des handlers pour recupere les information via ipc.

---

## Structure complète

```
plugins/note/
src
 ├── run.py          ← logique principale
 └── config.yaml
└── data
```

---

## Étape 1 — Les schémas (`plugin.yaml`)

```yaml
name: notes
version: "1.0.0"
framework_version: ">=1.0,<2.0"
execution_mode: sandboxed
description: "Plugin de gestion de notes — création, lecture, suppression, recherche"
author: "Exemple"
entry_point: "src/main.py"


# ── Limites de ressources ──────────────────────────────────
resources:
  timeout_seconds: 10        # temps max par appel handle() — lève IPCTimeoutError
  max_memory_mb: 128         # RAM max du subprocess (0 = illimité)
  max_disk_mb: 50            # quota total du répertoire data/ (0 = illimité)
  rate_limit:
    calls: 100               # appels max autorisés
    period_seconds: 60       # par fenêtre glissante de 60 secondes

# ── Configuration runtime ──────────────────────────────────
runtime:
  log_level: "INFO"          # DEBUG | INFO | WARNING | ERROR

  health_check:
    enabled: true
    interval_seconds: 30     # ping automatique toutes les 30s
    timeout_seconds: 3       # délai max pour la réponse au ping
  retry:
    max_attempts: 3          # nombre de tentatives sur erreur IPC
    backoff_seconds: 0.5     # délai initial (doublé à chaque retry)

# ── Permissions filesystem ─────────────────────────────────
filesystem:
  allowed_paths:
    - "data/"                # seul répertoire où le plugin peut écrire
  denied_paths:
    - "src/"                 # protection du code source
```

---

## Étape 2 — Le stockage (`main.py`)
### class NoteStore
```python
import json
from pathlib import Path
class NoteStore:
    """Persistance des notes dans un fichier JSON local."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def all(self) -> list[dict]:
        return list(self._data.values())

    def get(self, note_id: str) -> dict | None:
        return self._data.get(note_id)

    def set(self, note: dict) -> None:
        self._data[note["id"]] = note
        self._save()

    def delete(self, note_id: str) -> bool:
        if note_id not in self._data:
            return False
        del self._data[note_id]
        self._save()
        return True

    def lenf(self) -> int:
        return len(self._data)


```

### helper
```python
from datetime import datetime, timezone
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ok(**kwargs) -> dict:
    return {"status": "ok", **kwargs}

def _error(msg: str) -> dict:
    return {"status": "error", "msg": msg}
```
---
### class Principal `Plugin`
```python

class Plugin:
    """
    Plugin Sandboxed de gestion de notes.
    Toutes les données restent dans data/notes.json — aucun accès extérieur.
    """

    def __init__(self) -> None:
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        self.store = NoteStore(data_dir / "notes.json")

    async def handle(self, action: str, payload: dict) -> dict:
        """Point d'entrée unique — dispatche vers la bonne méthode."""
        handlers = {
            "ping": self._ping,
            "create": self._create,
            "get": self._get,
            "list": self._list,
            "update": self._update,
            "delete": self._delete,
            "search": self._search,
            "stats": self._stats,
        }

        handler = handlers.get(action)
        if handler is None:
            return _error(
                f"Action inconnue : {action!r}. "
                f"Actions disponibles : {list(handlers.keys())}"
            )

        try:
            return await handler(payload)
        except Exception as e:
            return _error(f"Erreur interne : {e}")

    # ──────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────

    async def _ping(self, payload: dict) -> dict:
        return _ok(msg="pong", plugin="notes", version="1.0.0")

    async def _create(self, payload: dict) -> dict:
        title = payload.get("title", "").strip()
        content = payload.get("content", "").strip()
        tags = payload.get("tags", [])

        if not title:
            return _error("Le champ 'title' est requis")
        if not isinstance(tags, list):
            return _error("'tags' doit être une liste")

        note = {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": content,
            "tags": [str(t) for t in tags],
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.store.set(note)
        return _ok(note=note)

    async def _get(self, payload: dict) -> dict:
        note_id = payload.get("id")
        if not note_id:
            return _error("Le champ 'id' est requis")

        note = self.store.get(note_id)
        if note is None:
            return _error(f"Note '{note_id}' introuvable")

        return _ok(note=note)

    async def _list(self, payload: dict) -> dict:
        notes = self.store.all()

        # Filtre par tag optionnel
        tag_filter = payload.get("tag")
        if tag_filter:
            notes = [n for n in notes if tag_filter in n.get("tags", [])]

        # Tri par date de création (plus récentes en premier)
        notes.sort(key=lambda n: n.get("created_at", ""), reverse=True)

        return _ok(notes=notes, count=len(notes))

    async def _update(self, payload: dict) -> dict:
        note_id = payload.get("id")
        if not note_id:
            return _error("Le champ 'id' est requis")

        note = self.store.get(note_id)
        if note is None:
            return _error(f"Note '{note_id}' introuvable")

        if "title" in payload:
            note["title"] = str(payload["title"]).strip()
        if "content" in payload:
            note["content"] = str(payload["content"]).strip()
        if "tags" in payload:
            if not isinstance(payload["tags"], list):
                return _error("'tags' doit être une liste")
            note["tags"] = [str(t) for t in payload["tags"]]

        note["updated_at"] = _now()
        self.store.set(note)
        return _ok(note=note)

    async def _delete(self, payload: dict) -> dict:
        note_id = payload.get("id")
        if not note_id:
            return _error("Le champ 'id' est requis")

        if not self.store.delete(note_id):
            return _error(f"Note '{note_id}' introuvable")

        return _ok(msg=f"Note '{note_id}' supprimée")

    async def _search(self, payload: dict) -> dict:
        query = payload.get("query", "").strip().lower()
        if not query:
            return _error("Le champ 'query' est requis")

        results = [
            note
            for note in self.store.all()
            if query in note.get("title", "").lower()
            or query in note.get("content", "").lower()
            or any(query in tag.lower() for tag in note.get("tags", []))
        ]

        results.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
        return _ok(results=results, count=len(results), query=query)

    async def _stats(self, payload: dict) -> dict:
        notes = self.store.all()
        all_tags: dict[str, int] = {}
        for note in notes:
            for tag in note.get("tags", []):
                all_tags[tag] = all_tags.get(tag, 0) + 1

        return _ok(
            total_notes=len(notes),
            total_tags=len(all_tags),
            tag_frequency=dict(
                sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
            ),
        )

    async def _len(self, payload: dict) -> dict:
        return _ok(count=self.store.lenf())

```
### Execution et test
1. lance l'app
    ```bash
        poetry run uvicorn main:app --reload
    ```
2. execute l'app
```bash
    curl -X POST http://localhos:8000/plugin/note/ping
```
reponse 
```json
    {
        "status":"ok",
        "msg": "pong",
        "plugin":"notes",
        "version": "1.0.0"

    }
```



## Points clés à retenir

- **`PLUGIN_INFO`** est obligatoire — sans lui, le `PluginLoader` rejette le plugin.
- **`class Plugin`** doit exister et hériter correctement via `super().__init__()`.
- Les routes sont définies **dans** la classe ou avec les décorateurs `@router.*` au niveau module.
- Utilisez `logging.getLogger("nom_plugin")` pour des logs traçables dans le monitoring.
- Les erreurs doivent lever des `HTTPException` FastAPI pour une réponse HTTP propre.

**Prochaine étape :** [Utiliser un plugin depuis un autre plugin ou service](./plugin-usage.md)
