# notes_manager — Plugin Sandboxed

Plugin de gestion de notes persistées localement.
Tourne dans un subprocess isolé, communique via IPC JSON.

## Structure

```
notes_manager/
├── plugin.yaml          # Manifeste
├── pyproject.toml       # Dépendances (stdlib uniquement ici)
├── src/
│   └── main.py          # Plugin — NoteStore + Plugin.handle()
└── data/
    └── notes.json       # Persistance automatique (créé au premier appel)
```

## Actions disponibles

### ping
Smoke test — vérifie que le plugin répond.
```json
POST /plugin/notes_manager/ping
{}
→ {"status": "ok", "msg": "pong", "plugin": "notes_manager", "version": "1.0.0"}
```

### create
```json
POST /plugin/notes_manager/create
{
  "payload": {
    "title": "Ma première note",
    "content": "Contenu de la note",
    "tags": ["perso", "important"]
  }
}
→ {
  "status": "ok",
  "note": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Ma première note",
    "content": "Contenu de la note",
    "tags": ["perso", "important"],
    "created_at": "2026-02-13T10:00:00+00:00",
    "updated_at": "2026-02-13T10:00:00+00:00"
  }
}
```

### get
```json
POST /plugin/notes_manager/get
{"payload": {"id": "550e8400-e29b-41d4-a716-446655440000"}}
→ {"status": "ok", "note": {...}}
```

### list
```json
POST /plugin/notes_manager/list
{"payload": {}}                         // toutes les notes
{"payload": {"tag": "important"}}       // filtrées par tag
→ {"status": "ok", "notes": [...], "count": 3}
```

### update
```json
POST /plugin/notes_manager/update
{
  "payload": {
    "id": "550e8400-...",
    "title": "Titre modifié",
    "tags": ["perso", "urgent"]
  }
}
→ {"status": "ok", "note": {...}}
```

### delete
```json
POST /plugin/notes_manager/delete
{"payload": {"id": "550e8400-..."}}
→ {"status": "ok", "msg": "Note '550e8400-...' supprimée"}
```

### search
```json
POST /plugin/notes_manager/search
{"payload": {"query": "important"}}
→ {"status": "ok", "results": [...], "count": 2, "query": "important"}
```

### stats
```json
POST /plugin/notes_manager/stats
{}
→ {
  "status": "ok",
  "total_notes": 5,
  "total_tags": 3,
  "tag_frequency": {"perso": 3, "important": 2, "urgent": 1}
}
```

## Exemple d'utilisation depuis le Core

```python
manager = PluginManager(plugins_dir="plugins", secret_key=b"...")
await manager.load_all()

# Créer une note
result = await manager.call("notes_manager", "create", {
    "title": "Réunion lundi",
    "content": "Préparer slides + démo plugin",
    "tags": ["travail", "urgent"]
})
note_id = result["note"]["id"]

# Rechercher
result = await manager.call("notes_manager", "search", {"query": "slides"})

# Stats
result = await manager.call("notes_manager", "stats", {})
```