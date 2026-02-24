# Utiliser les services existants

xcore fournit plusieurs services prêts à l'emploi dans `extensions/services/`. Ce tutoriel montre comment les utiliser dans vos plugins.

---

## Services disponibles

| Service | Dossier | Description |
|---------|---------|-------------|
| Auth / JWT | `auth/` | Authentification et gestion des sessions |
| Sécurité | `security/` | Hachage des mots de passe, tokens |
| Base de données | `database/` | Session SQLAlchemy |
| Cache | `cache/` | Client Redis |
| OTP | `otpprovider/` | Codes à usage unique |
| Admin | `admin/` | Rôles et permissions |

---

## Service d'authentification (`auth/`)

### Protéger une route

```python
from fastapi import APIRouter, Depends
from extensions.services.auth import get_current_user

router = APIRouter(prefix="/profil", tags=["profil"])

@router.get("/moi")
def mon_profil(user = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
    }
```

### Vérifier les rôles

```python
from extensions.services.auth import require_role

@router.delete("/{item_id}")
def supprimer(item_id: int, user = Depends(require_role("admin"))):
    # Seulement accessible aux admins
    ...
```

---

## Service de base de données (`database/`)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from extensions.services.database import get_db
from .models import MonModele  # vos modèles SQLAlchemy

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
def lister_items(db: Session = Depends(get_db)):
    return db.query(MonModele).all()

@router.post("/")
def creer_item(data: dict, db: Session = Depends(get_db)):
    item = MonModele(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
```

### Créer vos modèles SQLAlchemy

Placez vos modèles dans votre plugin et héritez de la `Base` partagée :

```python
# plugins/mon_plugin/models.py
from extensions.services.database import Base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class MonItem(Base):
    __tablename__ = "mon_plugin_items"
    
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## Service de cache (`cache/`)

```python
from fastapi import APIRouter, Depends
from extensions.services.cache import get_cache, CacheService
import json

router = APIRouter(prefix="/catalogue", tags=["catalogue"])

@router.get("/produits")
async def get_produits(cache: CacheService = Depends(get_cache)):
    # Vérifier le cache d'abord
    cached = await cache.get("produits:all")
    if cached:
        return json.loads(cached)
    
    # Charger les données (DB, API externe, etc.)
    produits = charger_produits_depuis_db()
    
    # Mettre en cache pour 5 minutes
    await cache.set("produits:all", json.dumps(produits), ttl=300)
    
    return produits
```

### Opérations de cache disponibles

```python
await cache.get("cle")                    # Lire
await cache.set("cle", "valeur", ttl=60) # Écrire (TTL en secondes)
await cache.delete("cle")                 # Supprimer
await cache.exists("cle")                 # Vérifier l'existence
await cache.flush_pattern("produits:*")   # Supprimer par pattern
```

---

## Service de sécurité (`security/`)

```python
from extensions.services.security import hash_password, verify_password, create_token

# Hasher un mot de passe
hashed = hash_password("mon_mot_de_passe")

# Vérifier un mot de passe
is_valid = verify_password("mon_mot_de_passe", hashed)

# Créer un token JWT
token = create_token({"user_id": 42, "role": "admin"})
```

---

## Service OTP (`otpprovider/`)

```python
from extensions.services.otpprovider import OTPService

otp_service = OTPService()

# Générer un code OTP
code = otp_service.generate(user_id=42)     # ex: "847291"
# Le code est stocké en mémoire/Redis avec une expiration

# Vérifier un code soumis par l'utilisateur
is_valid = otp_service.verify(user_id=42, code="847291")
```

---

## Combiner plusieurs services

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from extensions.services.database import get_db
from extensions.services.auth import get_current_user
from extensions.services.cache import get_cache

router = APIRouter(prefix="/tableau-de-bord", tags=["dashboard"])

@router.get("/stats")
async def stats(
    db: Session = Depends(get_db),
    cache = Depends(get_cache),
    user = Depends(get_current_user),
):
    cache_key = f"stats:user:{user.id}"
    
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Requête DB coûteuse
    stats = calculer_stats(db, user.id)
    await cache.set(cache_key, json.dumps(stats), ttl=120)
    
    return stats
```
