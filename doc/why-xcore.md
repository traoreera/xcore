---
title: Pourquoi xcore ?
description: Contexte d'usage, bénéfices pour les développeurs, et synergie avec l'IA.
icon: material/lightbulb-on
---

# Pourquoi xcore ?

---

## Le problème qu'il résout

Construire un backend Python en 2025 force un choix inconfortable :

| Approche | Avantage | Problème |
|----------|----------|---------|
| **Monolithe FastAPI** | Simple à démarrer, tout est là | Couplage fort — changer une feature touche tout le reste |
| **Microservices** | Isolation parfaite | Overhead opérationnel énorme : déploiements, service discovery, réseau |
| **Monolithe modulaire sans framework** | Bon compromis | Pas de standard — chaque équipe réinvente l'isolation, les services partagés, l'observabilité |

**xcore est la troisième voie** : un moteur d'orchestration de plugins qui donne l'isolation d'une architecture microservices avec la simplicité de déploiement d'un monolithe.

---

## Dans quel contexte l'utiliser ?

### ✅ xcore est fait pour toi si…

**Tu construis une plateforme SaaS multi-tenant**
: Isolation DB par schéma PostgreSQL, prefixage cache, jobs cloisonnés par tenant — sans écrire une ligne de plomberie.

**Tu as plusieurs équipes sur le même backend**
: Chaque équipe owne ses plugins. Pas de merge conflicts sur `main.py`. Pas de couplage sur les imports.

**Tu veux livrer vite sans sacrifier la qualité**
: Hot-reload en dev, signature HMAC des plugins en prod, scan AST avant exécution — le framework gère la sécurité, toi tu gères le métier.

**Tu dois intégrer du code tiers ou expérimental**
: Mode `sandboxed` : subprocess isolé, 43 modules bloqués, limites CPU/mémoire configurables. Un plugin planté ne tue pas le processus principal.

**Tu veux de l'observabilité sans la configurer**
: Logging structuré, métriques Prometheus, tracing OpenTelemetry, health checks liveness/readiness, profilage CPU/RSS — tout est branché dès le boot.

---

### ❌ xcore n'est pas fait pour toi si…

- Tu construis une API simple avec 3 endpoints — FastAPI seul suffit.
- Tu n'as qu'une feature métier et aucun plan d'évolution — pas besoin d'isolation.
- Tes contraintes infra imposent des microservices avec réseau et k8s par service — xcore est intra-processus.

---

## Comment il facilite la vie des développeurs

### 1. Zéro plomberie à écrire

Un plugin xcore, c'est une classe Python + un fichier YAML. Tu n'écris pas :

- la gestion du cycle de vie (chargement, hot-reload, arrêt propre)
- l'injection des services (DB, cache, scheduler)
- la configuration et son parsing
- la gestion des dépendances inter-plugins
- le routing HTTP

```python
# Tout ce qu'un plugin doit contenir
class Plugin(TrustedBase):
    async def on_load(self):
        self.db = self.get_service("db")

    async def handle(self, action, payload):
        if action == "create_order":
            await self.db.execute("INSERT INTO orders ...")
            return ok(order_id=42)
        return error("unknown action")
```

xcore s'occupe du reste.

---

### 2. Hot-reload sans redémarrage

En développement, xcore surveille les dossiers plugins. Modifier un fichier recharge uniquement ce plugin — le reste du système continue de tourner. Pas de `Ctrl+C / uvicorn --reload` qui redémarre tout.

---

### 3. Services injectés, pas importés

Au lieu d'instancier et gérer la DB dans chaque module :

```python
# Sans xcore — dans chaque plugin/module
engine = create_async_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine)
```

Avec xcore, la DB est dans le `ServiceContainer`. Tu y accèdes directement :

```python
self.db = self.get_service("db")
```

Changement de backend (PostgreSQL → MySQL) ? Une ligne dans `integration.yaml`, aucun changement dans les plugins.

---

### 4. Dépendances inter-plugins déclarées, pas codées

Si le plugin `billing` dépend du plugin `auth`, tu le déclares dans `plugin.yaml` :

```yaml
requires:
  - name: auth
    version: ">=1.0"
```

xcore charge `auth` en premier, vérifie la version, et bloque le démarrage si la dépendance est incompatible — avant même que ton code s'exécute.

---

### 5. Observabilité sans configuration

Dès qu'un plugin hérite de `TrustedBase` :

```python
self.logger.info("commande créée", order_id=42)       # structuré, namespaced
self.metrics.counter("orders_total").inc()             # Prometheus-ready
with self.tracer.span("payment") as span:              # OTel, propagé inter-plugins
    ...
```

Pas d'import, pas d'initialisation, pas de configuration. Tout est injecté.

---

## Comment il booste la productivité avec l'IA

xcore est architecturalement aligné avec la façon dont les LLMs génèrent du code.

### Contexte réduit = génération précise

Chaque plugin est **autonome et délimité** : une classe, un fichier YAML, un contrat clair (`handle(action, payload) → ok() | error()`). Quand tu demandes à un LLM de générer un plugin, il n'a pas besoin du contexte de toute ta codebase — juste du contrat xcore.

```
"Génère un plugin xcore qui reçoit action='send_invoice', envoie un email
via self.get_service('mail'), et retourne ok(invoice_id=...) ou error(...)"
```

Le LLM produit un plugin valide du premier coup parce que le contrat est standardisé.

---

### Scaffolding déterministe

La structure d'un plugin est toujours identique :

```
mon_plugin/
├── plugin.yaml
└── src/
    └── main.py
```

Les LLMs excellent à générer du code dans des structures répétitives et bien définies. xcore est une structure répétitive et bien définie.

---

### Tests isolés, faciles à générer

Chaque plugin est testable en isolation totale — pas besoin de monter toute l'application :

```python
async def test_create_order():
    plugin = Plugin(ctx=mock_context())
    result = await plugin.handle("create_order", {"items": [...]})
    assert result["status"] == "ok"
```

Demander à un LLM de générer les tests d'un plugin xcore produit du code directement exécutable sans adaptation.

---

### L'IA comme développeur de plugins

Dans une architecture xcore, l'IA peut générer un plugin entier — logique métier, tests, manifest — et le livrer dans un dossier. Le framework le charge à chaud, le scanne (mode sandboxed), et le déploie. **Aucun changement dans le core.**

C'est une boucle de développement IA-native :

```
Prompt → Plugin généré → Scan AST → Hot-reload → Test en prod
```

---

## En conclusion

xcore répond à un besoin précis : **construire des backends Python évolutifs sans payer le coût opérationnel des microservices**.

Il te donne :

- **L'isolation** sans la complexité réseau
- **Les services partagés** sans la plomberie
- **L'observabilité** sans la configuration
- **La sécurité** sans la friction

Et dans un contexte de développement assisté par IA, sa structure standardisée et ses contrats explicites font de chaque plugin une unité parfaite pour la génération, le test et le déploiement automatisés.

> xcore ne remplace pas FastAPI — il le complète. FastAPI gère le HTTP. xcore gère ce qui tourne derrière.
