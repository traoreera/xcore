# Architecture Overview

Plongée approfondie dans l'architecture interne de XCore : comment le kernel, les services et les plugins interagissent.

---

## 1. Vue d'Ensemble Haute Niveau

XCore suit le pattern **Modular Monolith**. Tous les plugins s'exécutent dans un environnement orchestré unifié, mais sont strictement isolés via des frontières logiques (injection de contexte) et physiques (sandbox au niveau processus).

```mermaid
flowchart TB
    subgraph Core["🎯 XCore Kernel"]
        direction TB
        X[⚙️ Xcore Engine<br/>Point d'entrée principal]
        PS[🔄 Plugin Supervisor<br/>Gestion cycle de vie]
        SC[🔧 Service Container<br/>Registry services]
        EB[📡 Event Bus<br/>Messagerie async]
        PE[🛡️ Permission Engine<br/>Contrôle d'accès]
    end
    
    subgraph Infra["🏗️ Infrastructure Partagée"]
        DB[(🗄️ Database<br/>SQL/NoSQL)]
        CACHE[(⚡ Cache<br/>Redis/Memory)]
        SCHED[⏰ Scheduler<br/>APScheduler]
        LOG[📝 Logger<br/>Structuré]
    end
    
    subgraph Plugins["🧩 Écosystème Plugins"]
        direction LR
        TP[🔐 Trusted Plugins<br/>Processus principal]
        SP[📦 Sandboxed Plugins<br/>Processus isolé]
    end
    
    subgraph App["🌐 Application"]
        FA[FastAPI<br/>Routes HTTP]
        WS[WebSocket<br/>Real-time]
    end
    
    App --> X
    X --> PS
    X --> SC
    X --> EB
    X --> PE
    
    SC --> Infra
    PS --> TP
    PS --> SP
    
    EB -.->|Pub/Sub| TP
    EB -.->|Pub/Sub| SP
    PE -.->|Audit| PS
    
    style Core fill:#E3F2FD,stroke:#1976D2,stroke-width:2px
    style Infra fill:#E8F5E9,stroke:#388E3C,stroke-width:2px
    style Plugins fill:#FFF3E0,stroke:#F57C00,stroke-width:2px
    style App fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
```

### Composants Clés

| Composant | Rôle | Analogie |
| :--- | :--- | :--- |
| **Xcore Engine** | Point d'entrée, coordonne le boot | Chef d'orchestre |
| **PluginSupervisor** | Lifecycle, hot-reload, IPC | Gestionnaire de processus |
| **ServiceContainer** | Registry DB, Cache, Scheduler | Boîte à outils partagée |
| **EventBus** | Dispatcher async Observer pattern | Système de notification |
| **PermissionEngine** | Policy-based access control | Garde de sécurité |

---

## 2. Boot Sequence Détaillée

Le framework suit une séquence d'initialisation stricte pour garantir que toutes les dépendances sont résolues avant le démarrage des plugins.

```mermaid
sequenceDiagram
    participant Dev as Développeur
    participant Main as main.py
    participant X as Xcore Engine
    participant Cfg as Config Loader
    participant S as Services
    participant L as PluginLoader
    participant DAG as Dependency Graph
    participant P as Plugins
    participant R as Router

    Dev->>Main: uvicorn app:app
    Main->>X: boot(app)
    
    Note over X: 📋 Phase 1: Configuration
    X->>Cfg: Charger xcore.yaml
    X->>Cfg: Charger .env
    Cfg-->>X: Config validée
    
    Note over X: 🔧 Phase 2: Services
    X->>S: Initialiser DB
    X->>S: Initialiser Cache
    X->>S: Initialiser Scheduler
    S-->>X: ✅ Services Ready
    
    Note over X: 🧩 Phase 3: Plugins
    X->>L: Découvrir plugins/
    L->>L: Parser plugin.yaml
    L->>DAG: Build dependency graph
    DAG->>DAG: Topological sort
    DAG-->>L: Ordre de chargement
    
    loop Chaque vague de plugins
        L->>P: Load plugin (trusted/sandboxed)
        P->>P: on_load()
        P-->>L: ✅ Ready
    end
    
    Note over X: 🌐 Phase 4: Routage
    X->>R: Monter routes FastAPI
    R->>R: Plugin routes
    R->>R: API routes
    R-->>X: ✅ Routes montées
    
    X-->>Main: Application prête
    Main-->>Dev: 🚀 Running on :8000
```

### Détails des Phases

```mermaid
gantt
    title Boot Sequence Timeline
    dateFormat X
    axisFormat %L
    
    section Configuration
    Charger YAML      :a1, 0, 10
    Charger ENV       :a2, after a1, 5
    Validation        :a3, after a2, 5
    
    section Services
    Database          :b1, after a3, 20
    Cache             :b2, after a3, 15
    Scheduler         :b3, after a3, 10
    
    section Plugins
    Discovery         :c1, after b1, 10
    DAG Build         :c2, after c1, 15
    Load Wave 1       :c3, after c2, 30
    Load Wave 2       :c4, after c3, 30
    
    section Routing
    Mount Routes      :d1, after c4, 10
```

---

## 3. Machine d'État des Plugins

Chaque plugin est géré par une **Finite State Machine (FSM)** pour assurer des transitions sûres pendant les hot-reloads ou en cas d'échec.

```mermaid
stateDiagram-v2
    [*] --> UNLOADED: Découverte
    
    UNLOADED --> LOADING: supervisor.load()
    
    state LOADING {
        [*] --> SCANNING: AST Scan
        SCANNING --> VALIDATING: Scan OK
        VALIDATING --> INSTANTIATING: Manifest OK
        INSTANTIATING --> INITIALIZING: Entry point OK
        INITIALIZING --> READY: on_load() OK
    end
    
    LOADING --> FAILED: Erreur AST
    LOADING --> FAILED: Erreur Manifest
    LOADING --> FAILED: Erreur on_load()
    
    READY --> RELOADING: supervisor.reload()
    
    state RELOADING {
        [*] --> UNLOADING: on_unload()
        UNLOADING --> RELOADING_CODE: Recharger code
        RELOADING_CODE --> RE_INITIALIZING: Nouveau on_load()
        RE_INITIALIZING --> READY: Succès
    end
    
    RELOADING --> FAILED: Échec reload
    
    READY --> UNLOADED: supervisor.unload()
    FAILED --> UNLOADED: Cleanup
    FAILED --> RELOADING: Retry (max 3)
    
    note right of READY
        🟢 État stable
        - Routes actives
        - Événements abonnés
        - Services connectés
    end note
    
    note right of FAILED
        🔴 État terminal
        - Erreur enregistrée
        - Cleanup requis
        - Notification envoyée
    end note
    
    note right of UNLOADED
        ⚪ État initial/final
        - Code non chargé
        - Aucune ressource
    end note
```

### Codes d'État

| État | Signification | Actions Possibles |
| :--- | :--- | :--- |
| `UNLOADED` | Plugin découvert mais non chargé | `load()` |
| `LOADING` | Initialisation en cours | Attendre |
| `READY` | Plugin opérationnel | `reload()`, `unload()`, `call()` |
| `RELOADING` | Mise à jour à chaud | Attendre |
| `FAILED` | Erreur irrécupérable | `unload()`, `reload()` (retry) |

---

## 4. Communication Inter-Plugins (IPC)

Quand le **Plugin A** appelle le **Plugin B**, l'appel n'est **jamais direct**. Il transite par le **Supervisor Pipeline** du kernel.

### Architecture du Pipeline

```mermaid
flowchart LR
    subgraph Caller["📤 Plugin A (Appelant)"]
        A[Code métier]
    end

    subgraph Kernel["🎯 XCore Supervisor Pipeline"]
        direction TB
        M1[📍 Tracing<br/>Génère span]
        M2[🛑 Rate Limiting<br/>Vérifie quota]
        M3[🔐 Permission Audit<br/>Valide autorisation]
        M4[🔄 Retry Logic<br/>Gère échecs]
    end

    subgraph Target["📥 Plugin B (Cible)"]
        B[Handler @action]
    end

    A -- "ctx.plugins.call()" --> M1
    M1 --> M2
    M2 --> M3
    M3 --> M4
    M4 -- "execute" --> B
    B -- "result" --> A
    
    style Kernel fill:#FFEBEE,stroke:#C62828,stroke-width:2px
    style M3 fill:#C62828,color:#fff
```

### Détail des Étapes du Pipeline

```mermaid
sequenceDiagram
    participant A as Plugin A
    participant T as Tracing
    participant R as RateLimit
    participant P as PermissionEngine
    participant L as RetryLogic
    participant B as Plugin B

    A->>T: call("plugin_b", "action", payload)
    
    Note over T: 1. Tracing
    T->>T: Créer span ID
    T->>T: Injecter context
    
    Note over R: 2. Rate Limiting
    R->>R: Vérifier quota A
    R-->>T: ✅ Dans la limite
    
    Note over P: 3. Permission Audit
    P->>P: Charger policies
    P->>P: Vérifier A → B.action
    P-->>T: ✅ Autorisé
    
    Note over L: 4. Retry Logic
    L->>B: Exécuter action
    alt Succès
        B-->>L: Résultat
        L-->>A: ✅ Résultat
    else Échec transitoire
        B-->>L: Erreur
        L->>L: Retry (max 3)
        L-->>A: ✅ Résultat (retry)
    else Échec permanent
        L-->>A: ❌ Erreur
    end
```

### Middleware Stack Détaillé

| Étape | Rôle | Détails |
| :--- | :--- | :--- |
| **Tracing** | Observabilité | Génère un span OpenTelemetry, propage le context |
| **Rate Limiting** | Protection | Vérifie le quota du caller (calls/période) |
| **Permission Audit** | Sécurité | Valide la policy `resource: action` |
| **Retry Logic** | Résilience | Retry exponentiel sur erreurs transitoires |

---

## 5. Modèle de Sandboxing

Les plugins sandboxed s'exécutent dans un **processus OS dédié**. C'est le niveau d'isolation le plus élevé.

### Architecture du Sandbox

```mermaid
flowchart TB
    subgraph Kernel["🎯 Kernel Process"]
        K[XCore Engine]
        PS[PluginSupervisor]
        WR[Worker Manager]
    end
    
    subgraph IPC["📡 JSON-RPC 2.0 Channel"]
        direction LR
        PIPE1[Pipe stdout]
        PIPE2[Pipe stdin]
    end
    
    subgraph Sandbox["📦 Sandbox Process"]
        SW[Sandbox Worker]
        AST[🛡️ AST Scanner]
        EX[Code Exécuté]
    end
    
    K --> PS
    PS --> WR
    WR --> IPC
    IPC --> Sandbox
    
    style Sandbox fill:#FFEBEE,stroke:#C62828
    style AST fill:#C62828,color:#fff
```

### Les 3 Couches de Protection

```mermaid
flowchart LR
    subgraph L1["Couche 1: AST Scan"]
        A1[Parser AST] --> A2[Forbidden Names]
        A2 --> A3[Import Whitelist]
    end
    
    subgraph L2["Couche 2: Process Isolation"]
        B1[Processus dédié] --> B2[JSON-RPC sur pipes]
        B2 --> B3[Pas de pickle]
    end
    
    subgraph L3["Couche 3: Resource Limits"]
        C1[Memory Monitor] --> C2[Timeout Monitor]
        C2 --> C3[Kill si dépassement]
    end
    
    L1 --> L2 --> L3
    
    style L1 fill:#FFE0B2,stroke:#F57C00
    style L2 fill:#C8E6C9,stroke:#388E3C
    style L3 fill:#BBDEFB,stroke:#1976D2
```

#### Couche 1: Analyse Statique (AST)

Avant exécution, l'`ASTScanner` parse l'arbre syntaxique du plugin :

```python
# Ce qui est BLOQUÉ :
import os          # ❌ Forbidden module
import subprocess  # ❌ Forbidden module
eval()             # ❌ Forbidden name
exec()             # ❌ Forbidden name
__class__          # ❌ Forbidden attribute
__globals__        # ❌ Forbidden attribute
__subclasses__()   # ❌ Forbidden attribute (sandbox escape)
```

#### Couche 2: Isolation Processus

```mermaid
sequenceDiagram
    participant K as Kernel
    participant P as Pipe (IPC)
    participant S as Sandbox Worker

    K->>P: {"jsonrpc":"2.0","method":"call",...}
    Note over P: JSON uniquement<br/>Pas d'objets Python
    P->>S: Désérialiser JSON
    S->>S: Exécuter handler
    S->>P: {"jsonrpc":"2.0","result":...}
    P->>K: Résultat JSON
```

#### Couche 3: Limites de Ressources

| Ressource | Limite | Action |
| :--- | :--- | :--- |
| **Mémoire (RSS)** | `max_memory_mb` | Kill process si dépassement |
| **Temps CPU** | `timeout_seconds` | Kill + timeout error |
| **Appels** | `rate_limit` | 429 Too Many Requests |

---

## 6. Service Scoping

Les services enregistrés dans le `ServiceContainer` ont différents niveaux de visibilité :

```mermaid
flowchart TB
    subgraph Container["🔧 Service Container"]
        direction TB
        PUB[🟢 Public Services<br/>db, cache, scheduler]
        PRI[🔴 Private Services<br/>Kernel interne]
        SCO[🟡 Scoped Services<br/>Plugins autorisés]
    end
    
    subgraph Access["Accès"]
        K[🎯 Kernel]
        T[🔐 Trusted Plugins]
        S[📦 Sandboxed Plugins]
    end
    
    PUB --> K
    PUB --> T
    PUB --> S
    
    PRI --> K
    
    SCO --> K
    SCO --> T
    SCO -.->|Si autorisé| S
    
    style PUB fill:#C8E6C9,stroke:#388E3C
    style PRI fill:#FFCDD2,stroke:#C62828
    style SCO fill:#FFF9C4,stroke:#F57F17
```

### Matrice d'Accès

| Scope | Description | Accès | Exemple |
| :--- | :--- | :--- | :--- |
| **Public** | Infrastructure générale | Kernel + Tous plugins | `db`, `cache`, `scheduler` |
| **Private** | Services kernel internes | Kernel uniquement | `permission_engine`, `plugin_supervisor` |
| **Scoped** | Restreint à plugins spécifiques | Plugins autorisés uniquement | `stripe_api` (plugin paiement) |

### Exemple de Configuration

```yaml
# xcore.yaml
services:
  # Service public - accessible par tous
  db:
    scope: public
    backend: postgresql
    url: ${DATABASE_URL}
  
  # Service scoped - accessible uniquement par authorized plugins
  payment_db:
    scope: scoped
    authorized_plugins:
      - stripe_plugin
      - billing_plugin
    backend: postgresql
    url: ${PAYMENT_DATABASE_URL}
  
  # Service private - kernel uniquement
  audit_log:
    scope: private
    backend: sqlite
```

---

## 7. Flux de Données Complet

Voici le flux complet d'une requête HTTP à travers XCore :

```mermaid
sequenceDiagram
    participant Client as 🌐 Client HTTP
    participant API as 📡 FastAPI Router
    participant X as ⚙️ XCore Engine
    participant P as 🛡️ Permission Engine
    participant S as 🔄 Plugin Supervisor
    participant PL as 🧩 Plugin Cible
    participant DB as 🗄️ Database

    Client->>API: POST /plugins/call
    API->>X: plugins.call(plugin, action, payload)
    
    Note over X,P: 1. Permission Check
    X->>P: verify(plugin, action)
    P-->>X: ✅ Autorisé
    
    Note over X,S: 2. Resolve Plugin
    X->>S: get_handler(plugin, action)
    S-->>X: Handler trouvé
    
    Note over S,PL: 3. Execute Action
    S->>PL: @action(payload)
    
    alt Besoin DB
        PL->>DB: Query
        DB-->>PL: Résultats
    end
    
    PL-->>S: Résultat
    S-->>X: Response
    X-->>API: JSON
    API-->>Client: HTTP 200 OK
```

---

## Prochaines Lectures

| 📚 Document | Objectif |
| :--- | :--- |
| [Technical Decisions](decisions.md) | Comprendre les choix architecturaux |
| [Security Deep Dive](../guides/security.md) | Détails du sandboxing |
| [Scaling Analysis](../guides/scaling.md) | Passage à l'échelle |
