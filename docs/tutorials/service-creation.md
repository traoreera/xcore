# Créer un service (extension)

Ce tutoriel explique comment créer un service partagé dans `extensions/services/`, utilisable par plusieurs plugins.

**Prérequis :** avoir lu [Plugins vs Extensions/Services](../concepts/plugins-vs-extensions.md)

---

## Quand créer un service ?

Créez un service lorsque vous identifiez une logique **réutilisée dans plusieurs plugins** :
- Connexion à une API externe (Stripe, Twilio, SendGrid...)
- Accès à une ressource partagée (file de messages, bucket S3...)
- Logique métier transversale (permissions, calculs, formatage...)

---

## Structure d'un service

```
extensions/services/
└── mon_service/
    ├── __init__.py
    ├── service.py      ← logique principale
    └── schemas.py      ← modèles Pydantic (optionnel)
```

Un service n'a **pas** de `PLUGIN_INFO`, pas de classe `Plugin`, et **n'expose pas de routes**. C'est un module Python classique.

---

## Exemple : service de formatage de données

Créons un service `formatter` qui normalise les données avant de les renvoyer.

### `service.py`

```python
# extensions/services/formatter/service.py
from typing import Any, Dict
from datetime import datetime

def format_response(data: Any, meta: Dict = None) -> Dict:
    """
    Enveloppe standardisée pour les réponses API des plugins.
    """
    return {
        "data": data,
        "meta": meta or {},
        "timestamp": datetime.utcnow().isoformat(),
        "success": True,
    }

def format_error(message: str, code: int = 400) -> Dict:
    """
    Format standardisé pour les erreurs.
    """
    return {
        "error": message,
        "code": code,
        "timestamp": datetime.utcnow().isoformat(),
        "success": False,
    }

def paginate(items: list, page: int, per_page: int) -> Dict:
    """
    Pagine une liste et retourne les métadonnées de pagination.
    """
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
    }
```

### `__init__.py`

```python
# extensions/services/formatter/__init__.py
from .service import format_response, format_error, paginate

__all__ = ["format_response", "format_error", "paginate"]
```

---

## Utiliser le service dans un plugin

```python
# plugins/mon_plugin/run.py
from fastapi import APIRouter, Request
from extensions.services.formatter import format_response, paginate

router = APIRouter(prefix="/articles", tags=["articles"])

ARTICLES = [{"id": i, "titre": f"Article {i}"} for i in range(1, 21)]

@router.get("/")
def list_articles(page: int = 1, per_page: int = 5, request: Request = None):
    result = paginate(ARTICLES, page, per_page)
    return format_response(result["items"], meta=result["pagination"])
```

Réponse :
```json
{
  "data": [{"id": 1, "titre": "Article 1"}, ...],
  "meta": {"page": 1, "per_page": 5, "total": 20, "pages": 4},
  "timestamp": "2025-01-15T10:30:00.000000",
  "success": true
}
```

---

## Service avec injection de dépendances FastAPI

Pour les services qui nécessitent une configuration ou une connexion, utilisez le pattern `Depends` :

```python
# extensions/services/storage_s3/service.py
import os
import boto3
from functools import lru_cache

class S3Service:
    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def upload(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"s3://{self.bucket}/{key}"

@lru_cache()
def get_s3_service() -> S3Service:
    return S3Service(
        bucket=os.getenv("S3_BUCKET", "mon-bucket"),
        region=os.getenv("AWS_REGION", "eu-west-1"),
    )
```

Dans le plugin :

```python
from fastapi import Depends
from extensions.services.storage_s3 import get_s3_service, S3Service

@router.post("/upload")
async def upload_fichier(
    fichier: bytes,
    s3: S3Service = Depends(get_s3_service)
):
    url = s3.upload(f"uploads/{fichier}", fichier)
    return {"url": url}
```

---

## Bonnes pratiques

- **Ne jamais importer** un plugin depuis un service (dépendance circulaire).
- Utilisez `@lru_cache()` pour les instances coûteuses à créer (connexions, clients HTTP).
- Gérez les erreurs dans le service et levez des exceptions Python — le plugin les transforme en `HTTPException` si nécessaire.
- Documentez les variables d'environnement requises dans un `README.md` ou `config.yaml` du service.
