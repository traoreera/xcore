# Foire Aux Questions (FAQ)

## Questions Générales

### Qu'est-ce que xcore ?

xcore est un framework ERP modulaire basé sur FastAPI qui permet de développer des applications extensibles via un système de plugins dynamiques. Il inclut une authentification JWT, une gestion des rôles et permissions, un moteur de templates Jinja2, et un système de hooks événementiels.

### Quels sont les cas d'usage principaux ?

- **Applications ERP** modulaires avec extensions plugins
- **Micro-services** avec chargement dynamique de modules
- **Plateformes SaaS** multi-tenant
- **Systèmes d'administration** avec interfaces personnalisables
- **APIs extensibles** avec hot-reload

### Quelle est la différence avec FastAPI standard ?

FastAPI est un framework web minimaliste. xcore ajoute :
- Système de plugins avec hot-reload
- Gestion des permissions et rôles (RBAC)
- Templates et composants UI
- Hooks événementiels
- Cache Redis intégré
- Tâches en arrière-plan

## Installation et Configuration

### Quelle version de Python est requise ?

Python 3.11 ou supérieur est recommandé. Le projet utilise Poetry pour la gestion des dépendances.

### Puis-je utiliser une autre base de données que SQLite ?

Oui, xcore supporte toute base de données compatible SQLAlchemy :
- SQLite (développement)
- PostgreSQL (recommandé production)
- MySQL/MariaDB
- Oracle
- Microsoft SQL Server

Modifiez simplement l'URL dans `config.json` :

```json
{
  "database": {
    "url": "postgresql://user:password@localhost/dbname"
  }
}
```

### Comment changer le port par défaut ?

```bash
uvicorn main:app --port 8080
```

Ou modifiez `config.json` :

```json
{
  "server": {
    "port": 8080
  }
}
```

### Où sont stockés les logs ?

Les logs sont stockés dans :
- `logs/app.log` - Logs applicatifs
- `logs/manager.log` - Logs du gestionnaire de plugins
- Console en mode développement

## Plugins

### Comment créer un plugin minimal ?

Structure minimale :

```
my_plugin/
├── __init__.py
├── run.py
└── plugin.json
```

```python
# run.py
from fastapi import APIRouter

PLUGIN_INFO = {
    "name": "my_plugin",
    "version": "1.0.0",
    "api_prefix": "/my_plugin",
    "tags": ["my_plugin"],
}

router = APIRouter(prefix="/my_plugin", tags=["my_plugin"])

@router.get("/")
async def hello():
    return {"message": "Hello from My Plugin!"}
```

### Le hot-reload ne fonctionne pas

Vérifiez :
1. Que le fichier `plugin.json` est valide
2. Que le dossier plugins est correctement configuré dans `config.json`
3. Les logs pour les erreurs de syntaxe
4. Que le plugin est marqué comme `active: true`

### Comment partager un plugin entre projets ?

Les plugins sont des packages Python standards. Vous pouvez :
1. Les publier sur PyPI
2. Les installer via `pip install -e ./mon_plugin`
3. Les copier dans le dossier `plugins/` de chaque projet

### Comment désactiver un plugin ?

```bash
# Via API
curl -X PUT http://localhost:8000/system/plugins/mon_plugin/disable \
  -H "Authorization: Bearer $TOKEN"
```

Ou modifiez `plugin.json` :

```json
{
  "active": false
}
```

### Les plugins peuvent-ils avoir leurs propres dépendances ?

Oui, créez un fichier `requirements.txt` dans le dossier du plugin :

```
requests==2.31.0
pandas==2.0.0
```

Le gestionnaire les installera automatiquement.

## Authentification et Sécurité

### Comment changer le secret JWT ?

Créez/modifiez un fichier `.env` :

```bash
JWT_SECRET_KEY=votre-nouvelle-cle-tres-longue-et-aleatoire-ici
```

Ou modifiez `config.json` :

```json
{
  "security": {
    "jwt_secret_key": "votre-nouvelle-cle"
  }
}
```

**Important** : Redémarrer l'application après modification.

### Comment configurer l'authentification 2FA ?

Le module `otpprovider` gère l'authentification à deux facteurs :

```python
from otpprovider.service import create_otp_device

# Créer un appareil OTP
device = await create_otp_device(user_id, "Mon Téléphone")

# Générer QR Code pour Google Authenticator
qr_code = device.get_qr_code_uri()
```

### Comment protéger une route spécifique ?

```python
from fastapi import Depends
from auth.routes import get_current_user
from admin.service import require_permission

@router.get("/admin-only")
async def admin_endpoint(
    user: User = Depends(get_current_user),
    _: None = Depends(require_permission("admin_access"))
):
    return {"message": "Admin access granted"}
```

### Où sont stockés les mots de passe ?

Les mots de passe sont hashés avec bcrypt et stockés dans la base de données. Seul le hash est conservé, jamais en clair.

## Base de Données

### Comment ajouter un nouveau modèle ?

1. Créez le modèle dans `database/models.py` ou dans votre plugin :

```python
from sqlalchemy import Column, Integer, String, DateTime
from database import Base

class MonModele(Base):
    __tablename__ = "mon_modele"

    id = Column(Integer, primary_key=True)
    nom = Column(String(255))
    created_at = Column(DateTime)
```

2. Créez une migration Alembic :

```bash
alembic revision --autogenerate -m "Ajout MonModele"
alembic upgrade head
```

### Comment utiliser les relations SQLAlchemy ?

```python
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    author_id = Column(Integer, ForeignKey("users.id"))

    author = relationship("User", back_populates="articles")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    articles = relationship("Article", back_populates="author")
```

### Comment faire une requête complexe ?

```python
from sqlalchemy import select, and_, or_
from database import get_db

async def get_filtered_articles(db: AsyncSession, user_id: int, status: str):
    query = select(Article).where(
        and_(
            Article.author_id == user_id,
            or_(
                Article.status == status,
                Article.status == "published"
            )
        )
    ).order_by(Article.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()
```

## Frontend et Templates

### Comment créer une page HTML ?

```python
from fastapi import Request
from frontend.config import engine

@router.get("/page")
async def render_page(request: Request):
    return engine.render(
        "ma_page.html",
        {
            "request": request,
            "title": "Ma Page",
            "data": mes_donnees
        }
    )
```

### Comment créer un composant réutilisable ?

Créez un fichier dans `templates/components/mon_composant.html` :

```html
<!-- components/mon_composant.html -->
<div class="mon-composant">
  <h3>{{ title }}</h3>
  <p>{{ content }}</p>
</div>
```

Utilisez-le dans un template :

```html
{% component "mon_composant" with title="Mon Titre" content="Mon contenu" %}
```

### Comment personnaliser le thème ?

Modifiez `frontend/config.py` :

```python
engine.set_theme("dark")  # ou "light", "cupcake", etc.
```

Les thèmes sont basés sur DaisyUI/TailwindCSS.

## Hooks et Événements

### Quand utiliser les hooks ?

Utilisez les hooks pour :
- Déclencher des actions après certains événements
- Étendre le comportement sans modifier le code source
- Créer des plugins réactifs

### Comment créer un hook personnalisé ?

```python
from hooks.hooks import hooks

# Émettre un événement
await hooks.emit("mon_plugin.action", {
    "user_id": 123,
    "action": "created"
})

# Écouter un événement
@hooks.on("mon_plugin.action")
async def handle_action(event):
    print(f"Action reçue: {event.data}")
```

### Les hooks sont-ils synchrones ou asynchrones ?

Les deux sont supportés :

```python
@hooks.on("event.sync")
def sync_handler(event):
    pass  # Synchrone

@hooks.on("event.async")
async def async_handler(event):
    pass  # Asynchrone
```

## Cache

### Comment mettre en cache une fonction ?

```python
from cache.decorators import cached

@cached(ttl=300)  # 5 minutes
async def get_expensive_data(id: int):
    # Cette fonction sera mise en cache
    return await fetch_from_db(id)
```

### Comment invalider le cache ?

```python
from cache.manager import cache_manager

# Invalider une clé spécifique
await cache_manager.delete("ma_cle")

# Invalider par pattern
await cache_manager.delete_pattern("users:*")
```

### Quels backends de cache sont supportés ?

- **Redis** (recommandé production)
- **In-memory** (développement)
- **Memcached**

## Déploiement

### Comment déployer en production ?

1. **Avec Docker** :

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY . .
RUN pip install poetry
RUN poetry install --no-dev

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **Avec Gunicorn** :

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

3. **Avec Systemd** :

Créez un service systemd pour le démarrage automatique.

### Comment configurer HTTPS ?

Utilisez un reverse proxy (Nginx, Traefik) ou Uvicorn avec SSL :

```bash
uvicorn main:app --ssl-keyfile=./key.pem --ssl-certfile=./cert.pem
```

### Comment scaler horizontalement ?

- Déployez plusieurs instances derrière un load balancer
- Utilisez Redis pour les sessions partagées
- Configurez une base de données centralisée (PostgreSQL)

## Performance

### Comment optimiser les performances ?

1. **Activez le cache** pour les données fréquemment accédées
2. **Utilisez des index** SQL sur les colonnes souvent filtrées
3. **Pagination** pour les listes longues
4. **Async/await** partout où c'est possible
5. **Connection pooling** pour la base de données

### Comment monitorer les performances ?

Activez les métriques dans `config.json` :

```json
{
  "monitoring": {
    "enabled": true,
    "prometheus_endpoint": "/metrics"
  }
}
```

## Dépannage

### L'application ne démarre pas

Vérifiez :
1. Les dépendances sont installées (`poetry install`)
2. Le fichier `config.json` est valide JSON
3. La base de données est accessible
4. Les ports ne sont pas déjà utilisés

### Erreur "Module not found"

```bash
# Réinstaller les dépendances
poetry install

# Vérifier le PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Les plugins ne se chargent pas

Vérifiez les logs et assurez-vous que :
1. Le dossier `plugins/` existe
2. Les plugins ont un `plugin.json` valide
3. Les fichiers Python n'ont pas d'erreurs de syntaxe

### Erreur de base de données "table not found"

```bash
# Exécuter les migrations
alembic upgrade head

# Ou recréer la base
rm app.db  # SQLite
alembic upgrade head
```

## Contribution

### Comment contribuer au projet ?

1. Fork le repository
2. Créez une branche (`git checkout -b feature/ma-feature`)
3. Commitez vos changements
4. Poussez vers votre fork
5. Ouvrez une Pull Request

### Comment signaler un bug ?

Créez une issue sur GitHub avec :
- Version de xcore
- Version de Python
- Étapes pour reproduire
- Logs d'erreur

### Où trouver de l'aide ?

- Documentation : `/docs`
- Issues GitHub
- Discussions GitHub
- Discord/Slack (si disponible)

## Questions Spécifiques

### Puis-je utiliser xcore avec une application React/Vue ?

Oui, xcore expose une API REST complète. Configurez CORS dans `main.py` :

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Comment gérer les uploads de fichiers ?

```python
from fastapi import UploadFile, File

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    # Sauvegarder le fichier...
    return {"filename": file.filename}
```

### Comment implémenter la pagination ?

```python
from fastapi import Query

@router.get("/items")
async def list_items(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    skip = (page - 1) * per_page
    items = await get_items(skip=skip, limit=per_page)
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": await count_items()
    }
```

### Comment créer une commande CLI ?

Ajoutez dans `pyproject.toml` :

```toml
[tool.poetry.scripts]
ma_commande = "mon_module.cli:main"
```

Puis créez `mon_module/cli.py` :

```python
import typer

app = typer.Typer()

@app.command()
def ma_commande(nom: str):
    print(f"Bonjour {nom}!")

if __name__ == "__main__":
    app()
```

## Liens Utiles

- [Documentation Complète](README.md)
- [Guide des Plugins](plugins.md)
- [API Reference](api/endpoints.md)
- [GitHub Repository](https://github.com/votre-repo/xcore)
