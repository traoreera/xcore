"""
notes_manager — Plugin Sandboxed
──────────────────────────────────
Gestion de notes persistées dans data/notes.json.

Actions disponibles :
    ping          → smoke test
    create        → crée une note
    get           → récupère une note par id
    list          → liste toutes les notes (avec filtre optionnel)
    update        → met à jour le contenu d'une note
    delete        → supprime une note
    search        → recherche full-text dans les notes
    stats         → statistiques globales ewdnk
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ──────────────────────────────────────────────
# Stockage JSON simple
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(**kwargs) -> dict:
    return {"status": "ok", **kwargs}


def _error(msg: str) -> dict:
    return {"status": "error", "msg": msg}


# ──────────────────────────────────────────────
# Plugin
# ──────────────────────────────────────────────

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
            "ping":   self._ping,
            "create": self._create,
            "get":    self._get,
            "list":   self._list,
            "update": self._update,
            "delete": self._delete,
            "search": self._search,
            "stats":  self._stats,
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
        return _ok(msg="pong", plugin="notes_manager", version="1.0.0")

    async def _create(self, payload: dict) -> dict:
        title   = payload.get("title", "").strip()
        content = payload.get("content", "").strip()
        tags    = payload.get("tags", [])

        if not title:
            return _error("Le champ 'title' est requis")
        if not isinstance(tags, list):
            return _error("'tags' doit être une liste")

        note = {
            "id":         str(uuid.uuid4()),
            "title":      title,
            "content":    content,
            "tags":       [str(t) for t in tags],
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
            note["title"]   = str(payload["title"]).strip()
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
            note for note in self.store.all()
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