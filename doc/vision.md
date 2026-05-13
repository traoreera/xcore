# XCore — Vision et Évolution

> *Un framework évolue dans son domaine quand il anticipe les besoins de ses utilisateurs avant qu'ils les formulent.*

Ce document explore les directions naturelles d'évolution de xcore en restant fidèle à sa philosophie fondamentale : **un noyau minimal, une extensibilité maximale, une isolation totale**.

---

## Là où en est xcore aujourd'hui

xcore est un **orchestrateur de plugins plugin-first** sur FastAPI. Son cœur de valeur est l'**isolation** : deux plugins dans la même application ne se connaissent pas — ils communiquent par événements, actions IPC ou services partagés. Le kernel arbitre tout.

```
FastAPI
  └── Xcore Kernel
        ├── Plugin Supervisor    (charge, décharge, surveille)
        ├── Service Container    (DB, Cache, Scheduler, Celery)
        ├── Event Bus            (messagerie async découplée)
        ├── Permission Engine    (RBAC par plugin)
        └── Sandbox              (isolation processus OS)
```

Ce modèle résout un problème réel : **comment construire une application modulaire sans payer le coût des microservices**. Mais ce même modèle peut être porté beaucoup plus loin.

---

## Axe 1 — Multi-tenancy natif

### Le problème actuel

xcore isole les plugins entre eux, mais tous les plugins voient les mêmes services, les mêmes données, le même cache. Pour une application SaaS multi-tenant, le développeur doit gérer lui-même l'isolation des données.

### La direction

Introduire une couche **tenant** comme concept de première classe dans le kernel. Chaque requête porte un `tenant_id` résolu automatiquement. Les services s'adaptent.

```yaml
# integration.yaml
multitenancy:
  enabled: true
  resolver: header        # header | jwt_claim | subdomain | path
  header_name: X-Tenant-ID
  isolation:
    database: schema      # schema | database | row_level
    cache: prefix         # prefix | namespace | isolated
```

```python
# Dans un plugin — aucun changement de code
@action("get_orders")
async def get_orders(self, payload: dict) -> dict:
    # self.db est automatiquement scopé au tenant courant
    async with self.db.session() as session:
        orders = await session.execute(select(Order))
    return ok(orders=[...])
```

```python
# Le kernel injecte le contexte tenant dans chaque service
class TenantAwareSession:
    async def __aenter__(self):
        session = await self._pool.acquire()
        await session.execute(f"SET search_path TO tenant_{self._tenant_id}")
        return session
```

**Impact** : xcore devient nativement utilisable pour des plateformes SaaS sans aucune plomberie supplémentaire.

---

## Axe 2 — Plugin Federation (appels cross-nœuds)

### Le problème actuel

`ctx.plugins.call("mon_plugin", "action", {})` fonctionne uniquement en local. Si le plugin est déployé sur un autre nœud, l'appel échoue.

### La direction

Transformer le `PluginSupervisor` en **registre distribué**. Un plugin peut être local ou distant — l'appelant ne sait pas la différence.

```yaml
# integration.yaml
federation:
  enabled: true
  registry: redis          # redis | consul | etcd
  transport: http          # http | grpc | amqp
  this_node:
    id: "node-paris-01"
    advertise: "http://paris-01.internal:8000"
```

```python
# Appel identique — le kernel résout local vs distant
result = await ctx.plugins.call("payment_plugin", "charge", {
    "amount": 4900,
    "currency": "EUR",
})
# Si payment_plugin est sur node-london-02, le kernel le route automatiquement
```

```python
# Déclaration dans plugin.yaml — "je peux être appelé à distance"
federation:
  exportable: true
  actions:
    - charge
    - refund
  # health et inspect restent toujours locaux
```

**Impact** : le modèle Monolith Modulaire devient un modèle **Cluster Modulaire** — les plugins se distribuent sans changer une ligne de leur code.

---

## Axe 3 — Schema Registry pour les actions de plugin

### Le problème actuel

Quand un plugin change la signature d'une action (renomme un champ, change un type), les autres plugins qui l'appellent cassent silencieusement au runtime.

### La direction

Introduire un **registre de schémas versionné** pour chaque action exposée. Le kernel valide les appels entrants et sortants et gère la compatibilité.

```python
from xcore.sdk import action, schema

class Plugin(TrustedBase):

    @action("create_user")
    @schema(
        version="2.0",
        input={
            "email": str,
            "role": Literal["admin", "user"],
        },
        output={
            "user_id": int,
            "created_at": datetime,
        },
        deprecated_fields={"username": "Supprimé en v2.0 — utiliser email"},
        breaking_since="2.0",
    )
    async def create_user(self, payload: dict) -> dict:
        ...
```

```bash
# CLI — vérifier la compatibilité avant déploiement
xcore plugin validate plugins/auth_plugin --check-breaking
# ✗  auth_plugin v2.0 : action "create_user" — champ "username" supprimé
#    3 plugin(s) appellent cette action avec ce champ : billing, dashboard, reports
```

**Impact** : refactoring de plugins en toute confiance, détection des breaking changes avant la production.

---

## Axe 4 — Plugins IA / Agents LLM

### Le problème actuel

Les LLMs (Claude, GPT, Gemini) sont de plus en plus utilisés pour automatiser des actions dans les applications. Aujourd'hui, les intégrer dans xcore demande d'écrire un plugin custom complet.

### La direction

Introduire `AgentBase` — un type de plugin qui expose ses actions comme des **outils LLM** et peut orchestrer d'autres plugins via le langage naturel.

```python
from xcore.sdk import AgentBase, tool, action

class SupportAgent(AgentBase):
    """Agent de support client — répond aux tickets en orchestrant les plugins."""

    model = "claude-sonnet-4-6"      # configuré dans plugin.yaml

    # Les @tool sont automatiquement exposés au LLM
    @tool("Recherche un utilisateur par email")
    async def find_user(self, email: str) -> dict:
        return await self.ctx.plugins.call("users", "find", {"email": email})

    @tool("Rembourse une commande")
    async def refund_order(self, order_id: int, reason: str) -> dict:
        return await self.ctx.plugins.call("billing", "refund", {
            "order_id": order_id,
            "reason": reason,
        })

    # L'action principale — le LLM orchestre les tools pour répondre
    @action("handle_ticket")
    async def handle_ticket(self, payload: dict) -> dict:
        response = await self.think(
            system="Tu es un agent de support. Résous le ticket en utilisant les outils disponibles.",
            user=payload["message"],
            context={"user_id": payload.get("user_id")},
        )
        return ok(reply=response.text, actions_taken=response.tool_calls)
```

```yaml
# plugin.yaml
name: support_agent
execution_mode: trusted
agent:
  model: claude-sonnet-4-6
  max_turns: 10
  allowed_plugins:           # seuls ces plugins peuvent être appelés
    - users
    - billing
    - orders
```

**Impact** : transformer n'importe quelle application xcore en application augmentée par l'IA — sans changer le code existant des plugins.

---

## Axe 5 — Hot-swap de services à l'exécution

### Le problème actuel

Changer de backend de cache (memory → redis) ou de base de données nécessite un redémarrage. En production, ce n'est pas acceptable.

### La direction

Permettre le remplacement d'un service sans downtime via le CLI ou l'API interne.

```bash
# Remplacer le backend de cache sans redémarrage
xcore services swap cache \
  --backend redis \
  --url redis://prod-redis-2:6379/0 \
  --migrate               # migre les clés existantes avant de basculer

# Output :
# ⏳ Nouveau backend initialisé (redis://prod-redis-2:6379/0)
# ⏳ Migration : 14 820 clés transférées (2.3s)
# ✓  Cache basculé — zéro requête perdue
```

```python
# API programmatique dans un plugin Trusted
await self.ctx.services.swap("cache", CacheConfig(
    backend="redis",
    url="redis://prod-redis-2:6379/0",
))
```

Mécanisme : le `ServiceContainer` maintient une référence stable. Les plugins gardent leur référence — c'est le proxy interne qui change de cible.

**Impact** : opérations de maintenance sans downtime, blue/green sur les services de données.

---

## Axe 6 — Plugin Composition

### Le problème actuel

Si deux plugins partagent beaucoup de logique (ex: `billing_stripe` et `billing_paypal`), le développeur duplique le code ou crée un plugin "base" fragile.

### La direction

Introduire les **traits** — des comportements réutilisables injectés dans un plugin.

```python
from xcore.sdk import TrustedBase, trait

# Définir un trait partagé
class BillingTrait:
    async def validate_amount(self, amount: int) -> bool:
        return 50 <= amount <= 1_000_000

    async def log_transaction(self, txn_id: str, amount: int) -> None:
        await self.ctx.events.emit("billing.transaction", {
            "txn_id": txn_id,
            "amount": amount,
            "plugin": self.name,
        })

# Utiliser le trait dans plusieurs plugins
@trait(BillingTrait)
class StripePlugin(TrustedBase):
    @action("charge")
    async def charge(self, payload: dict) -> dict:
        if not await self.validate_amount(payload["amount"]):  # hérité du trait
            return error("amount_invalid")
        result = await self._stripe.charge(payload["amount"])
        await self.log_transaction(result.id, payload["amount"])  # hérité
        return ok(charge_id=result.id)

@trait(BillingTrait)
class PaypalPlugin(TrustedBase):
    @action("charge")
    async def charge(self, payload: dict) -> dict:
        if not await self.validate_amount(payload["amount"]):
            return error("amount_invalid")
        ...
```

**Impact** : réutilisabilité sans héritage profond, composition explicite et testable.

---

## Axe 7 — Observabilité native OpenTelemetry

### Le problème actuel

xcore a des métriques et traces basiques. En production, les équipes utilisent Datadog, Grafana, Jaeger — et l'intégration est manuelle.

### La direction

Faire de chaque appel plugin, événement et action service un **span OpenTelemetry automatique**.

```yaml
observability:
  tracing:
    enabled: true
    backend: opentelemetry
    endpoint: "http://jaeger:4317"
    auto_instrument:
      plugins: true           # chaque @action devient un span
      services: true          # chaque requête DB/cache devient un span
      events: true            # chaque emit/subscribe devient un span
      http: true              # requêtes entrantes/sortantes
```

```
Trace : POST /plugin/orders/create_order
│
├── [2ms]  xcore.plugin.call → orders.create_order
│    ├── [1ms]  xcore.db.session → SELECT users WHERE id=42
│    ├── [0.3ms] xcore.cache.get → order:draft:42
│    └── [8ms]  xcore.worker.send → emails.order_confirmation
│         └── [async] celery.task → emails.send_welcome
│
└── [0.1ms] xcore.event.emit → orders.created
     ├── xcore.plugin.call → inventory.reserve (subscriber 1)
     └── xcore.plugin.call → analytics.track (subscriber 2)
```

**Impact** : visibilité totale sur le comportement de l'application en production, sans aucun code d'instrumentation.

---

## Axe 8 — Plugin Marketplace et écosystème

### Le problème actuel

Le marketplace xcore existe mais l'écosystème de plugins communautaires est embryonnaire.

### La direction

Faire du marketplace le **hub central** de l'écosystème, avec des garanties de qualité et de sécurité automatiques.

```bash
# Publier un plugin
xcore marketplace publish plugins/my_auth_plugin \
  --version 1.2.0 \
  --sign                    # signature automatique avec la clé du compte

# Le marketplace exécute automatiquement :
# ✓  Validation du manifeste
# ✓  Scan de sécurité (imports interdits, vulnérabilités connues)
# ✓  Tests de compatibilité (xcore >= 2.0)
# ✓  Sandbox smoke test
# → Publié : https://marketplace.xcore.dev/plugins/my_auth_plugin
```

```yaml
# plugin.yaml — métadonnées marketplace
marketplace:
  category: authentication
  tags: [jwt, oauth2, session]
  compatible_with:
    xcore: ">=2.1"
    python: ">=3.11"
  dependencies:
    - name: cache_plugin
      version: ">=1.0"
      optional: false
```

**Impact** : des plugins prêts à l'emploi pour les cas d'usage les plus courants (auth, paiement, email, analytics) — installables en une commande.

---

## Récapitulatif — Feuille de route

```
v2.x (court terme)
├── v2.2  Observabilité OpenTelemetry native
├── v2.3  Schema Registry pour les actions
└── v2.4  Plugin Traits (composition)

v3.x (moyen terme)
├── v3.0  Multi-tenancy natif
├── v3.1  Hot-swap de services
└── v3.2  Agents IA (AgentBase)

v4.x (long terme)
├── v4.0  Plugin Federation (cluster distribué)
└── v4.1  Marketplace avec écosystème communautaire
```

---

## Le fil directeur

Chaque axe respecte la même contrainte : **les plugins existants ne changent pas**. L'évolution de xcore se fait dans le kernel, dans les services, dans les outils — jamais en cassant le contrat avec les développeurs de plugins.

C'est ce qui distingue un framework d'un outil : un framework évolue sans trahir ceux qui lui font confiance.
