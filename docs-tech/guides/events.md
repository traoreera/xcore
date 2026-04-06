# Event & Hook System

XCore propose deux mécanismes de communication découplée : les **Événements** (asynchrones, side-effects) et les **Hooks** (synchrones, transformation de données).

---

## Vue d'Ensemble Comparative

```mermaid
flowchart LR
    subgraph Events["📡 Événements (Async)"]
        E1[Fire-and-forget]
        E2[Handlers parallèles]
        E3[Pas de retour]
        E4[Side effects]
    end
    
    subgraph Hooks["🪝 Hooks (Sync)"]
        H1[Transformation]
        H2[Séquentiel]
        H3[Retour valeur]
        H4[Inline logic]
    end
    
    Events -.->|Découplage fort| Hooks
    Hooks -.->|Transformation| Events
    
    style Events fill:#E3F2FD,stroke:#1976D2
    style Hooks fill:#FFF3E0,stroke:#F57C00
```

---

## 1. Système d'Événements Asynchrones

L'Event Bus est utilisé pour la communication **"fire-and-forget"**. Idéal pour déclencher des side effects (logging, emails, cache) après une action.

### Architecture de l'Event Bus

```mermaid
flowchart TB
    subgraph Publisher["📤 Publishers"]
        P1[Plugin A]
        P2[Plugin B]
        K[Kernel]
    end
    
    subgraph EventBus["📡 Event Bus"]
        direction TB
        Q[Queue Async]
        D[Dispatcher]
        R[Registry Handlers]
    end
    
    subgraph Subscriber["📥 Subscribers"]
        S1[Handler 1]
        S2[Handler 2]
        S3[Handler 3]
    end
    
    P1 --> EventBus
    P2 --> EventBus
    K --> EventBus
    
    EventBus --> S1
    EventBus --> S2
    EventBus --> S3
    
    style EventBus fill:#E8F5E9,stroke:#388E3C
```

### Concepts Clés

| Concept | Description | Usage |
| :--- | :--- | :--- |
| **Priority** | Les handlers avec priorité haute (100) s'exécutent avant les bas (50) | Ordonnancer l'exécution |
| **Propagation** | Un handler peut appeler `event.stop_propagation()` | Stopper la chaîne |
| **Gather** | Par défaut, handlers exécutés en parallèle via `asyncio.gather` | Performance |

---

### S'abonner à un Événement

```python
from xcore.sdk import TrustedBase, on, Event

class Plugin(TrustedBase):
    
    async def on_load(self):
        # Méthode 1: Décorateur (recommandé)
        # Le handler est automatiquement abonné
        
        # Méthode 2: Subscription manuelle
        self.ctx.events.on("user.created", self._on_user_created, priority=100)
    
    @on("user.created", priority=100)
    async def _on_user_created(self, event: Event):
        """
        Handler pour l'événement user.created
        
        Args:
            event: Contient data, timestamp, source
        """
        user_id = event.data.get("id")
        email = event.data.get("email")
        
        self.logger.info(f"Nouvel utilisateur créé: {user_id}")
        
        # Side effect: envoyer email de bienvenue
        await self._send_welcome_email(email)
        
        # Optionnel: stopper la propagation
        # event.stop_propagation()
    
    async def _send_welcome_email(self, email: str):
        # ... logique d'envoi ...
        pass
```

### Émettre un Événement

```python
from xcore.sdk import TrustedBase, action, ok

class Plugin(TrustedBase):
    
    @action("create_user")
    async def create_user(self, payload: dict):
        # 1. Créer l'utilisateur
        user_id = await self._create_in_db(payload)
        
        # 2. Émettre l'événement
        await self.ctx.events.emit("user.created", {
            "id": user_id,
            "email": payload.get("email"),
            "created_at": self._now()
        })
        
        # 3. Retourner résultat (l'événement est fire-and-forget)
        return ok(user_id=user_id)
```

### Flux d'un Événement

```mermaid
sequenceDiagram
    participant P as Plugin Publisher
    participant EB as Event Bus
    participant H1 as Handler 1 (priority=100)
    participant H2 as Handler 2 (priority=50)
    participant H3 as Handler 3 (priority=50)

    P->>EB: emit("user.created", data)
    
    Note over EB: Registry handlers par priority
    EB->>H1: _on_user_created(event)
    
    par Exécution parallèle (asyncio.gather)
        EB->>H2: handler_2(event)
        EB->>H3: handler_3(event)
    end
    
    H1-->>EB: ✅ Done
    H2-->>EB: ✅ Done
    H3-->>EB: ✅ Done
    
    EB-->>P: ✅ Tous handlers exécutés
    
    Note over P,H3: ⚠️ Le publisher n'attend pas<br/>les résultats des handlers
```

---

## 2. Événements Système Built-in

XCore émet plusieurs événements système que vous pouvez subscriber.

### Tableau des Événements Système

| Événement | Quand | Payload | Usage Typique |
| :--- | :--- | :--- | :--- |
| `xcore.plugins.booted` | Tous plugins chargés | `{"report": {...}}` | Initialisation globale |
| `plugin.<name>.loaded` | Plugin chargé | `{"name", "version"}` | Logging, metrics |
| `plugin.<name>.reloaded` | Plugin rechargé | `{"name"}` | Refresh cache |
| `plugin.<name>.unloaded` | Plugin déchargé | `{"name"}` | Cleanup |
| `permission.deny` | Permission refusée | `{"plugin", "resource", "action"}` | Audit sécurité |
| `security.violation` | Scan AST échoué | `{"plugin", "errors"}` | Alertes sécurité |
| `user.created` | Custom: utilisateur créé | `{"id", "email"}` | Welcome email |
| `user.deleted` | Custom: utilisateur supprimé | `{"id"}` | Cleanup données |

### Exemple: Subscriber aux Événements Système

```python
from xcore.sdk import TrustedBase, on, Event

class Plugin(TrustedBase):
    
    @on("xcore.plugins.booted", priority=200)
    async def _on_system_boot(self, event: Event):
        """Exécuté quand TOUS les plugins sont chargés."""
        report = event.data.get("report", {})
        loaded_count = report.get("loaded", 0)
        self.logger.info(f"🚀 Système prêt : {loaded_count} plugins chargés")
    
    @on("plugin.auth_plugin.loaded", priority=100)
    async def _on_auth_ready(self, event: Event):
        """Exécuté quand le plugin auth est prêt."""
        self.logger.info("✅ Plugin auth disponible")
        # Initialiser la connexion avec le plugin auth
    
    @on("permission.deny", priority=50)
    async def _on_permission_denied(self, event: Event):
        """Logging de toutes les permissions refusées."""
        plugin = event.data.get("plugin")
        resource = event.data.get("resource")
        self.logger.warning(f"🚫 Permission refusée: {plugin} → {resource}")
```

---

## 3. Best Practices pour les Événements

```mermaid
flowchart TB
    subgraph Do["✅ Bonnes Pratiques"]
        D1[Handlers légers]
        D2[Priorités claires]
        D3[Cleanup handlers]
        D4[Événements nommés]
    end
    
    subgraph Dont["❌ Erreurs à Éviter"]
        A1[Tâches lourdes]
        A2[Priorités magiques]
        A3[Memory leaks]
        A4[Noms obscurs]
    end
    
    Do -.->|Au lieu de| Dont
    
    style Do fill:#E8F5E9,stroke:#388E3C
    style Dont fill:#FFEBEE,stroke:#C62828
```

### 1. Handlers Légers

```python
# ❌ MAUVAIS: Handler lourd (bloque l'event loop)
@on("user.created")
async def bad_handler(self, event):
    # Envoi email synchrone (lent !)
    send_email_sync(event.data["email"])
    
    # Traitement lourd
    for i in range(1000000):
        process(i)

# ✅ BON: Déléguer au scheduler
@on("user.created")
async def good_handler(self, event):
    # Quick: queue la tâche
    await self.scheduler.add_job(
        self._send_welcome_email,
        args=[event.data["email"]]
    )
```

### 2. Priorités Explicites

```python
# ❌ MAUVAIS: Priorités arbitraires
@on("user.created", priority=42)
@on("user.created", priority=99)

# ✅ BON: Priorités sémantiques
PRIORITY_LOGGING = 100      # Logging en premier
PRIORITY_BUSINESS = 50      # Logique métier
PRIORITY_CLEANUP = 10       # Cleanup en dernier

@on("user.created", priority=PRIORITY_LOGGING)
@on("user.created", priority=PRIORITY_BUSINESS)
```

### 3. Nommage des Événements

```python
# ❌ MAUVAIS: Noms obscurs
await self.ctx.events.emit("stuff.happened", data)
await self.ctx.events.emit("do_thing", data)

# ✅ BON: Noms sémantiques (domain.event)
await self.ctx.events.emit("user.created", data)
await self.ctx.events.emit("user.deleted", data)
await self.ctx.events.emit("order.completed", data)
```

### 4. Stop Propagation (Usage Avancé)

```python
from xcore.sdk import TrustedBase, on, Event

class Plugin(TrustedBase):
    
    @on("user.created", priority=100)
    async def validate_user(self, event: Event):
        """Validation en premier, peut bloquer les autres handlers."""
        if not self._is_valid(event.data):
            self.logger.error("Utilisateur invalide")
            event.stop_propagation()  # ⚠️ Stop les handlers suivants
            return
        
    @on("user.created", priority=50)
    async def send_welcome(self, event: Event):
        """Ne s'exécute que si validation passe."""
        if event.propagation_stopped:
            self.logger.debug("Propagation stoppée, skip welcome")
            return
        
        # Envoyer email...
```

---

## 4. Hooks Synchrones

Les hooks permettent de modifier des données ou d'exécuter de la logique synchrone pendant un processus spécifique.

### Architecture du HookManager

```mermaid
flowchart LR
    subgraph Filters["🔄 Filters (Transformation)"]
        F1[Value] --> F2[Hook 1]
        F2 --> F3[Hook 2]
        F3 --> F4[Hook 3]
        F4 --> F5[Modified Value]
    end
    
    subgraph Actions["⚡ Actions (Side Effects)"]
        A1[Trigger] --> A2[Hook 1]
        A2 --> A3[Hook 2]
        A3 --> A4[Hook 3]
        A4 --> A5[Done]
    end
    
    style Filters fill:#E3F2FD,stroke:#1976D2
    style Actions fill:#FFF3E0,stroke:#F57C00
```

### A. Filters (Transformation de Données)

Les filters permettent de "faire passer une valeur dans une chaîne" pour laisser d'autres plugins la modifier.

```mermaid
flowchart LR
    V[Valeur Originale] --> H1[Hook 1]
    H1 -->|Modifie| H2[Hook 2]
    H2 -->|Modifie| H3[Hook 3]
    H3 -->|Modifie| R[Valeur Finale]
    
    style V fill:#E8F5E9
    style R fill:#C8E6C9
```

```python
# Côté Kernel ou Plugin
class Plugin(TrustedBase):
    
    async def render_page(self):
        # 1. Valeur de base
        title = "Bienvenue sur XCore"
        
        # 2. Appliquer les filters
        title = self.ctx.hooks.apply_filters("page_title", title)
        
        # title peut maintenant être modifié par d'autres plugins
        # Ex: "Bienvenue sur XCore | Dashboard"
        
        return f"<h1>{title}</h1>"
    
    # 3. Enregistrer un filter
    @filter("page_title")
    def modify_title(self, title: str) -> str:
        """Ajoute le suffixe au titre."""
        return f"{title} | Mon App"
```

### B. Actions (Side Effects Sync)

Les actions sont des side effects synchrones qui ne retournent pas de valeur.

```python
# Côté Kernel ou Plugin
class Plugin(TrustedBase):
    
    async def render_template(self, template_name: str):
        # 1. Trigger action avant rendu
        self.ctx.hooks.do_action("before_render", template=template_name)
        
        # 2. Rendu du template
        result = self._render(template_name)
        
        # 3. Trigger action après rendu
        self.ctx.hooks.do_action("after_render", template=template_name, result=result)
        
        return result
    
    # 4. Enregistrer un action hook
    @action_hook("before_render")
    def on_before_render(self, template: str):
        """Log chaque rendu de template."""
        self.logger.debug(f"Rendu du template: {template}")
```

---

## 5. Différence Entre Events et Hooks

| Caractéristique | Events | Hooks |
| :--- | :--- | :--- |
| **Exécution** | Asynchrone (`async def`) | Synchrone (`def`) |
| **Retourne Valeur** | ❌ Non | ✅ Oui (Filters) |
| **Parallèle** | ✅ Oui (`asyncio.gather`) | ❌ Non (Séquentiel) |
| **Propagation** | ✅ `stop_propagation()` | ❌ N/A |
| **Priorités** | ✅ Oui | ⚠️ Ordre d'enregistrement |
| **Use Case** | Side effects découplés | Transformation de données |

### Quand Utiliser Quoi ?

```mermaid
flowchart TB
    Start{Besoin ?}
    
    Start -->|Modifier données| Hooks
    Start -->|Side effect| Events
    
    Start -->|Synchrone requis| Hooks
    Start -->|Async OK| Events
    
    Start -->|Plusieurs listeners| Events
    Start -->|Chaîne transformation| Hooks
    
    Hooks --> H[🪝 Hooks]
    Events --> E[📡 Events]
    
    style H fill:#FFF3E0,stroke:#F57C00
    style E fill:#E3F2FD,stroke:#1976D2
```

### Exemple Comparatif

```python
# 📡 EVENT: Pour side effect découplé
@on("user.created")
async def send_welcome_email(self, event):
    # Envoi email async (ne modifie pas les données)
    await self.email_service.send(event.data["email"])

# 🪝 HOOK FILTER: Pour modifier des données
@filter("user.profile_data")
def add_premium_badge(self, profile_data: dict) -> dict:
    # Modifie les données avant retour
    if self._is_premium(user_id):
        profile_data["badge"] = "premium"
    return profile_data

# 🪝 HOOK ACTION: Pour side effect synchrone
@action_hook("before_user_save")
def log_user_change(self, user_data: dict):
    # Logging synchrone
    self.logger.debug(f"User update: {user_data}")
```

---

## 6. Exemple Complet: Système de Notification

```python
from xcore.sdk import TrustedBase, on, action, ok, filter

class NotificationPlugin(TrustedBase):
    """
    Plugin de notification qui démontre Events + Hooks.
    """
    
    async def on_load(self):
        # S'abonner aux événements système
        self.ctx.events.on("user.created", self._on_user_created, priority=50)
        self.ctx.events.on("order.completed", self._on_order_completed, priority=50)
    
    @on("user.created")
    async def _on_user_created(self, event):
        """Envoyer email de bienvenue."""
        email = event.data.get("email")
        await self._send_email(email, "Bienvenue !")
    
    @on("order.completed")
    async def _on_order_completed(self, event):
        """Envoyer confirmation de commande."""
        email = event.data.get("email")
        await self._send_email(email, "Commande confirmée !")
    
    @filter("notification.message")
    def add_disclaimer(self, message: str) -> str:
        """Ajouter un disclaimer à tous les messages."""
        return f"{message}\n\n-- Ceci est un message automatique"
    
    @action("send_notification")
    async def send_notification(self, payload: dict):
        """Action publique pour envoyer une notification."""
        # Appliquer les filters
        message = self.ctx.hooks.apply_filters(
            "notification.message",
            payload.get("message", "")
        )
        
        # Émettre un événement pour logging
        await self.ctx.events.emit("notification.sent", {
            "to": payload.get("to"),
            "message": message
        })
        
        return ok(status="sent")
```

---

## 7. Debugging et Monitoring

### Voir les Handlers Enregistrés

```bash
# Lister tous les handlers d'événements
xcore events list

# Lister tous les hooks
xcore hooks list
```

### Tracing des Événements

```python
# Activer le debug logging
# xcore.yaml
logging:
  level: DEBUG
  events: true  # Log tous les événements émis
```

### Diagnostic des Problèmes

| Problème | Cause Possible | Solution |
| :--- | :--- | :--- |
| Handler non appelé | Mauvais nom d'événement | Vérifier le nom exact |
| Handler appelé trop tard | Priorité trop basse | Augmenter priority |
| Memory leak | Handler non unsubscribed | Unsubscribe dans `on_unload` |
| Event loop bloquée | Handler trop lourd | Déléguer au scheduler |

---

## Prochaines Lectures

| 📚 Guide | Objectif |
| :--- | :--- |
| [Creating Plugins](creating-plugins.md) | Développer des plugins |
| [Services](services.md) | Utiliser les services partagés |
| [Monitoring](monitoring.md) | Observer les événements en prod |
