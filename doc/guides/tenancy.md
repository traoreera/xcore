# Multi-Tenancy

xcore embarque un système multi-tenant **transparent** : les plugins n'écrivent jamais de code lié au tenant. Le framework injecte l'isolation au niveau des services (cache, DB, scheduler) et filtre les appels IPC via `allowed_callers`.

---

## Activation

```yaml
# integration.yaml
tenancy:
  enabled: true              # false = mode mono-tenant "default" (zéro overhead)
  header: "X-Tenant-ID"     # header HTTP lu pour identifier le tenant
  subdomain: false           # true = acme.monapp.com → tenant "acme"
  default_tenant: "default"  # fallback si aucun header / subdomain trouvé

  isolate_cache: true        # préfixe automatique des clés Redis par tenant_id
  isolate_db: true           # SET search_path TO <tenant_id> (PostgreSQL)
  isolate_scheduler: false   # préfixe les job_id APScheduler par tenant_id
  enforce_ipc: true          # vérifie allowed_callers sur les appels IPC
```

---

## Extraction du tenant

Ordre de priorité :

1. **Header HTTP** `X-Tenant-ID: acme`
2. **Sous-domaine** `acme.monapp.com` → `"acme"` (si `subdomain: true`)
3. **Fallback** `default_tenant`

```
GET /api/orders HTTP/1.1
X-Tenant-ID: acme
```

Quand `enabled: false`, xcore injecte toujours `default_tenant` sans lire le header.

---

## Isolation des services

Les plugins accèdent aux services exactement comme en mode mono-tenant. xcore wrappe les services en arrière-plan.

### Cache

```python
class Plugin(AutoDispatchMixin, TrustedBase):
    @action("get_balance")
    async def get_balance(self, payload: dict) -> dict:
        cache = self.ctx.services.get("cache")

        # Le plugin écrit :
        balance = await cache.get("balance")

        # xcore stocke réellement :
        # "acme:balance" pour le tenant "acme"
        # "beta:balance" pour le tenant "beta"

        return ok(balance=balance)
```

**Méthodes disponibles :**

| Méthode | Comportement |
|:--------|:-------------|
| `get(key)` | lit `{tenant}:{key}` |
| `set(key, value, ttl=None)` | écrit `{tenant}:{key}` |
| `delete(key)` | supprime `{tenant}:{key}` |
| `exists(key)` | vérifie `{tenant}:{key}` |
| `incr(key, delta=1)` | incrémente `{tenant}:{key}` |
| `keys(pattern)` | retourne les clés **sans préfixe** |
| `clear(pattern)` | supprime les clés du tenant courant uniquement |

### Base de données (PostgreSQL)

```python
@action("list_orders")
async def list_orders(self, payload: dict) -> dict:
    db = self.ctx.services.get("db")

    # Le plugin écrit du SQL standard
    rows = await db.fetch_all("SELECT * FROM orders")
    # xcore a exécuté SET search_path TO acme, public avant
    # → les tables sont résolues dans le schéma "acme"

    return ok(orders=rows)
```

Avant chaque requête, xcore exécute :
```sql
SET search_path TO acme, public
```

Pour MySQL / SQLite, cette instruction est silencieusement ignorée.

**Adapters nommés** : si vous avez plusieurs bases (`analytics`, `reporting`…), xcore détecte et wrappe automatiquement tous les adapters `AsyncSQLAdapter`.

### Scheduler

```python
@action("schedule_report")
async def schedule_report(self, payload: dict) -> dict:
    scheduler = self.ctx.services.get("scheduler")

    # Le plugin déclare un job sans préfixe
    scheduler.add_job(generate_report, id="monthly_report", trigger="cron", hour=2)
    # xcore stocke "acme:monthly_report"

    return ok(scheduled=True)
```

`get_jobs()` retourne uniquement les jobs du tenant courant.

Activer avec `isolate_scheduler: true` dans `integration.yaml`.

---

## Autorisation IPC

Chaque plugin déclare dans `plugin.yaml` les plugins autorisés à l'appeler :

```yaml
# plugins/inventory/plugin.yaml
name: inventory
version: "1.0.0"
allowed_callers:
  - billing
  - dashboard
```

**Règle deny-by-default :** liste vide ou absente = tout IPC refusé.

```yaml
# Aucun plugin ne peut appeler inventory via IPC
allowed_callers: []
```

Les appels HTTP directs (`caller=None`) ne sont **jamais** filtrés.

### Appel IPC depuis un plugin

```python
class BillingPlugin(AutoDispatchMixin, TrustedBase):

    @action("generate_invoice")
    async def generate_invoice(self, payload: dict) -> dict:
        # caller="billing" et tenant_id injectés automatiquement
        stock = await self.call_plugin("inventory", "check_stock", {
            "sku": payload["sku"]
        })

        if stock.get("available", 0) < payload["quantity"]:
            return error("Stock insuffisant", "out_of_stock")

        # ... créer la facture
        return ok(invoice_id=42)
```

Le `caller` et le `tenant_id` sont propagés sans aucune configuration manuelle.

---

## Architecture interne

```
Requête HTTP (X-Tenant-ID: acme)
    │
    ▼
TenantMiddleware
    ├─ lit header / subdomain
    └─ injecte request.state.tenant_id = "acme"
    │
    ▼
Router FastAPI
    └─ extrait tenant_id depuis request.state
    │
    ▼
PluginSupervisor.call("plugin", "action", payload, tenant_id="acme")
    │
    ├─► IPCAuthMiddleware   ← bloque si caller ∉ allowed_callers
    ├─► TracingMiddleware
    ├─► RateLimitMiddleware
    ├─► PermissionMiddleware
    ├─► RetryMiddleware
    │
    ▼
_dispatch()
    ├─ instance.ctx.tenant_id = "acme"
    └─ instance.ctx.services = wrap_services_for_tenant(services, "acme")
            ├─ cache      → TenantAwareCache (préfixe "acme:")
            ├─ db         → TenantAwareDB (search_path=acme)
            ├─ analytics  → TenantAwareDB (auto-détecté)
            └─ scheduler  → TenantAwareScheduler (si isolate_scheduler)
```

---

## Provisioning PostgreSQL

xcore ne crée pas les schémas automatiquement. Pour chaque nouveau tenant :

```sql
-- Créer le schéma
CREATE SCHEMA IF NOT EXISTS acme;

-- Migrer les tables dans le schéma (exemple Alembic)
-- alembic upgrade head --schema acme
```

Ou via script Python :

```python
from sqlalchemy import text
async with db.session() as sess:
    await sess.execute(text("CREATE SCHEMA IF NOT EXISTS :s"), {"s": "acme"})
    await sess.commit()
```

---

## Accéder au tenant_id dans un plugin

```python
class Plugin(AutoDispatchMixin, TrustedBase):

    @action("whoami")
    async def whoami(self, payload: dict) -> dict:
        # tenant_id est toujours disponible dans ctx
        tenant = self.ctx.tenant_id
        return ok(tenant=tenant)
```

---

## Désactivation partielle

```yaml
tenancy:
  enabled: true
  isolate_cache: true    # cache isolé
  isolate_db: false      # DB partagée (schéma unique)
  isolate_scheduler: false
  enforce_ipc: false     # IPC libre (déconseillé en prod)
```

---

## Tests

```bash
# Tests unitaires (sans Redis / PostgreSQL)
poetry run pytest tests/unit/kernel/test_tenancy.py -v

# Tests d'intégration
poetry run pytest tests/integration/test_tenancy_integration.py -v

# Tous les tests tenancy
poetry run pytest -k "tenancy" -v
```
