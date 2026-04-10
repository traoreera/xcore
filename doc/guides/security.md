# Security Deep Dive

XCore suit un modèle **"Zero Trust"** pour les plugins. Même les plugins trusted sont restreints de modifier l'état du kernel, tandis que les plugins sandboxed sont isolés aux niveaux OS et Runtime.

---

## Vue d'Ensemble de la Sécurité

```mermaid
flowchart TB
    subgraph Defense["Défense en Profondeur"]
        direction TB
        L1[🛡️ Couche 1: AST Scan<br/>Analyse statique]
        L2[🛡️ Couche 2: Process Isolation<br/>Sandbox OS]
        L3[🛡️ Couche 3: Resource Limits<br/>Memory/CPU]
        L4[🛡️ Couche 4: Permissions<br/>Policy Engine]
        L5[🛡️ Couche 5: Signature<br/>HMAC Verification]
    end
    
    subgraph Attaques["Attaques Bloquées"]
        A1[Code Injection]
        A2[Sandbox Escape]
        A3[DoS Resource]
        A4[Accès Non Autorisé]
        A5[Tampering]
    end
    
    L1 -.->|Bloque| A1
    L2 -.->|Bloque| A2
    L3 -.->|Bloque| A3
    L4 -.->|Bloque| A4
    L5 -.->|Bloque| A5
    
    style Defense fill:#E8F5E9,stroke:#388E3C
    style L1 fill:#C8E6C9
    style L2 fill:#C8E6C9
    style L3 fill:#C8E6C9
    style L4 fill:#C8E6C9
    style L5 fill:#C8E6C9
```

---

## 1. Le Multi-Layer Sandbox

Quand `execution_mode: sandboxed` est défini, le kernel applique **3 couches de protection** successives.

### Vue d'Ensemble du Flux

```mermaid
flowchart LR
    subgraph PreExec["Pré-Exécution"]
        A[Code Source] --> B[🔍 AST Scanner]
        B --> C{Scan OK ?}
        C -->|Non| D[❌ Rejeté]
        C -->|Oui| E[📦 Spawn Worker]
    end
    
    subgraph Exec["Exécution"]
        E --> F[📡 JSON-RPC IPC]
        F --> G[⏱️ Timeout Monitor]
        G --> H[🧠 Memory Monitor]
    end
    
    subgraph PostExec["Post-Exécution"]
        H --> I{Limites OK ?}
        I -->|Non| J[❌ Kill Worker]
        I -->|Oui| K[✅ Résultat]
    end
    
    style PreExec fill:#FFF3E0,stroke:#F57C00
    style Exec fill:#E3F2FD,stroke:#1976D2
    style PostExec fill:#E8F5E9,stroke:#388E3C
```

---

### Couche 1: Analyse Statique (AST)

Avant l'exécution, l'`ASTScanner` parse l'arbre syntaxique du plugin avec un `ast.NodeVisitor`.

```mermaid
flowchart TB
    subgraph AST["🔍 AST Scanner"]
        S[Code Source] --> P[Parser AST]
        P --> N[NodeVisitor]
        
        N --> F1[Forbidden Names]
        N --> F2[Forbidden Attributes]
        N --> F3[Import Whitelist]
        
        F1 --> B1[❌ eval, exec]
        F1 --> B2[❌ globals, locals]
        F1 --> B3[❌ __import__]
        
        F2 --> B4[❌ __class__]
        F2 --> B5[❌ __globals__]
        F2 --> B6[❌ __subclasses__]
        
        F3 --> B7[❌ os, subprocess]
        F3 --> B8[❌ socket, requests]
    end
    
    style AST fill:#FFEBEE,stroke:#C62828
    style B1 fill:#FFCDD2
    style B2 fill:#FFCDD2
    style B3 fill:#FFCDD2
    style B4 fill:#FFCDD2
    style B5 fill:#FFCDD2
    style B6 fill:#FFCDD2
    style B7 fill:#FFCDD2
    style B8 fill:#FFCDD2
```

#### Liste Complète des Restrictions

```python
# ❌ Forbidden Names (bloqués par l'AST)
FORBIDDEN_NAMES = {
    'eval', 'exec', 'compile',
    'globals', 'locals', 'vars',
    '__import__', 'open', 'input',
    'breakpoint', 'delattr', 'setattr'
}

# ❌ Forbidden Attributes (sandboxes escapes courants)
FORBIDDEN_ATTRIBUTES = {
    '__class__', '__bases__', '__subclasses__',
    '__globals__', '__code__', '__closure__',
    '__builtins__', '__import__', 'gi_frame',
    'cr_frame', 'f_globals', 'f_locals'
}

# ❌ Forbidden Modules (nécessite allowed_imports)
FORBIDDEN_MODULES = {
    'os', 'sys', 'subprocess', 'multiprocessing',
    'socket', 'requests', 'urllib', 'http',
    'pickle', 'marshal', 'shelve'
}
```

#### Exemple de Configuration

```yaml
# plugin.yaml
# Pour utiliser des modules normalement restreints
allowed_imports:
  - datetime      # ✅ Autorisé
  - json          # ✅ Autorisé
  - hashlib       # ✅ Autorisé (si besoin)
  - re            # ✅ Autorisé

# Tentative d'import bloqué :
# import os  # ❌ Erreur: Module 'os' non autorisé
```

---

### Couche 2: Isolation Processus

Les plugins sandboxed s'exécutent dans un **processus OS dédié** via le module `multiprocessing`.

```mermaid
sequenceDiagram
    participant K as 🎯 Kernel Process
    participant M as 📡 Multiprocessing Manager
    participant W as 📦 Sandbox Worker
    
    Note over K: Boot du kernel
    K->>M: spawn_worker(plugin_path)
    
    Note over M: Création processus
    M->>W: fork()/spawn()
    W->>W: Charger code plugin
    
    Note over K,W: Communication via pipes
    K->>W: {"jsonrpc":"2.0","method":"call",...}
    Note over K,W: JSON uniquement<br/>⚠️ Pas de pickle !
    
    W->>W: Exécuter handler
    W->>K: {"jsonrpc":"2.0","result":...}
    
    Note over K: Désérialiser résultat
```

#### Transport: JSON-RPC 2.0 sur Pipes OS

```python
# Format des messages Kernel → Worker
{
    "jsonrpc": "2.0",
    "id": "uuid-1234-5678",
    "method": "call",
    "params": {
        "action": "greet",
        "payload": {"name": "World"}
    }
}

# Format des messages Worker → Kernel
{
    "jsonrpc": "2.0",
    "id": "uuid-1234-5678",
    "result": {"status": "ok", "message": "Hello !"}
}

# Ou en cas d'erreur
{
    "jsonrpc": "2.0",
    "id": "uuid-1234-5678",
    "error": {
        "code": -32000,
        "message": "Action not found"
    }
}
```

#### Pourquoi JSON-RPC ?

| Avantage | Description |
| :--- | :--- |
| **Sérialisation sûre** | Seulement types JSON (pas de `pickle` → pas de RCE) |
| **Langage-agnostique** | Pourrait être implémenté dans tout langage |
| **Debug-friendly** | Messages lisibles en clair |
| **Standardisé** | Spécification JSON-RPC 2.0 |

---

### Couche 3: Limites de Ressources OS

Le kernel monitorle RSS (Resident Set Size) et le temps CPU du worker.

```mermaid
flowchart LR
    subgraph Monitors["📊 Resource Monitors"]
        MM[🧠 Memory Monitor<br/>RSS Tracker]
        TM[⏱️ Timeout Monitor<br/>Execution Timer]
        CM[📈 CPU Monitor<br/>CPU Time Tracker]
    end
    
    subgraph Limits["⚠️ Limites"]
        ML[Max: max_memory_mb]
        TL[Max: timeout_seconds]
        CL[Max: cpu_seconds]
    end
    
    subgraph Actions["🔥 Actions"]
        MA[⚠️ Warning]
        KA[❌ Kill Process]
        RA[📝 Log Violation]
    end
    
    MM --> ML --> MA --> KA
    TM --> TL --> KA
    CM --> CL --> KA
    
    style Monitors fill:#E3F2FD,stroke:#1976D2
    style Limits fill:#FFF3E0,stroke:#F57C00
    style Actions fill:#FFEBEE,stroke:#C62828
```

#### Configuration des Limites

```yaml
# plugin.yaml
resources:
  # Mémoire maximale (Mo)
  max_memory_mb: 256
  
  # Timeout d'exécution (secondes)
  timeout_seconds: 30
  
  # Rate limiting
  rate_limit:
    calls: 1000
    period_seconds: 60
```

#### Comportement en Cas de Dépassement

| Ressource | Limite | Comportement |
| :--- | :--- | :--- |
| **Mémoire** | `max_memory_mb` | Warning à 80%, Kill à 100% |
| **Timeout** | `timeout_seconds` | Kill immédiat + erreur timeout |
| **Rate Limit** | `calls/period` | Erreur 429 Too Many Requests |

---

## 2. Permission Engine

Chaque appel inter-plugin et accès service est audité par le **PermissionEngine**.

### Modèle d'Évaluation

```mermaid
flowchart TB
    subgraph Evaluation["🔍 Évaluation Permission"]
        Start[Début Évaluation]
        CheckDeny[Vérifier DENY explicite ?]
        CheckAllow[Vérifier ALLOW explicite ?]
        DefaultDeny[❌ DENY par défaut]
        Allow[✅ ALLOW]
        Deny[❌ DENY]
    end
    
    Start --> CheckDeny
    CheckDeny -->|Oui| Deny
    CheckDeny -->|Non| CheckAllow
    CheckAllow -->|Oui| Allow
    CheckAllow -->|Non| DefaultDeny
    
    style Deny fill:#FFCDD2,stroke:#C62828
    style Allow fill:#C8E6C9,stroke:#388E3C
    style DefaultDeny fill:#FFCDD2,stroke:#C62828
```

### Modèle "Fail-Closed"

XCore utilise un modèle **"Fail-Closed"** : si aucune policy n'autorise explicitement une action, elle est **refusée**.

```
1. Vérifier DENY explicite → Si trouvé: ❌ REFUSÉ
2. Vérifier ALLOW explicite → Si trouvé: ✅ AUTORISÉ
3. Aucun match → ❌ REFUSÉ (défaut)
```

### Patterns de Permissions

#### Wildcards sur les Ressources

```yaml
permissions:
  # ✅ Autorise lecture sur TOUTES les tables 'users_*'
  - resource: "db.users.*"
    actions: ["read"]
    effect: allow
  
  # ✅ Autorise lecture/écriture sur cache global
  - resource: "cache.global"
    actions: ["read", "write"]
    effect: allow
  
  # ✅ Autorise TOUS les actions sur une resource
  - resource: "logs.*"
    actions: ["*"]
    effect: allow
  
  # ❌ DENY explicite (priorité haute)
  - resource: "db.admin.*"
    actions: ["*"]
    effect: deny
```

#### Exemple Complet de Policy

```yaml
# plugin.yaml
permissions:
  # Lecture seule sur la DB principale
  - resource: "db.main.users"
    actions: ["read"]
    effect: allow
  
  - resource: "db.main.posts"
    actions: ["read"]
    effect: allow
  
  # Écriture sur cache
  - resource: "cache.global"
    actions: ["read", "write"]
    effect: allow
  
  # Accès scheduler
  - resource: "scheduler.jobs"
    actions: ["create", "delete"]
    effect: allow
  
  # Interdiction explicite (sécurité défense)
  - resource: "db.admin.*"
    actions: ["*"]
    effect: deny
  
  - resource: "kernel.*"
    actions: ["*"]
    effect: deny
```

### Flux d'Évaluation

```mermaid
sequenceDiagram
    participant A as Plugin A
    participant S as Supervisor
    participant P as PermissionEngine
    participant L as Policy Loader

    A->>S: call("plugin_b", "get_user")
    S->>P: evaluate("plugin_a", "plugin_b.get_user")
    
    P->>L: Charger policies de plugin_a
    L-->>P: Retourner rules
    
    P->>P: Vérifier DENY explicite
    Note over P: ❌ Aucun DENY trouvé
    
    P->>P: Vérifier ALLOW explicite
    Note over P: ✅ Rule trouvée !
    
    P-->>S: ✅ Autorisé
    S->>A: Procéder à l'appel
```

---

## 3. Signature des Plugins Trusted

En production, le mode `strict_trusted` garantit que les plugins trusted n'ont pas été altérés.

### Architecture de Signature

```mermaid
flowchart TB
    subgraph Sign["📝 Signature (Développement)"]
        D1[Fichiers Plugin] --> D2[Calcul HMAC-SHA256]
        D2 --> D3[Générer plugin.sig]
    end
    
    subgraph Verify["🔍 Vérification (Production)"]
        V1[Charger plugin.sig] --> V2[Re-calculer hashes]
        V2 --> V3{Match ?}
        V3 -->|Oui| V4[✅ Charger]
        V3 -->|Non| V5[❌ Rejeté]
    end
    
    Sign --> Verify
    
    style Sign fill:#E8F5E9,stroke:#388E3C
    style Verify fill:#FFEBEE,stroke:#C62828
```

### Générer une Signature

```bash
# Signer un plugin trusted
xcore plugin sign plugins/my_plugin/

# Le fichier plugin.sig est créé/mis à jour
```

### Structure de `plugin.sig`

```json
{
  "plugin": "my_plugin",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "files": {
    "plugin.yaml": "a1b2c3d4e5f6...",
    "src/main.py": "f6e5d4c3b2a1...",
    "src/utils.py": "1234567890ab..."
  },
  "signature": "hmac-sha256-signature-here"
}
```

### Vérification au Boot

```mermaid
sequenceDiagram
    participant K as Kernel
    participant S as SignatureVerifier
    participant F as Fichiers Plugin
    participant Sig as plugin.sig

    K->>S: verify_trusted("my_plugin")
    
    S->>Sig: Charger signature
    S->>F: Lire fichiers actuels
    S->>S: Calculer hashes actuels
    
    S->>S: Comparer avec plugin.sig
    alt Hashes correspondent
        S-->>K: ✅ Vérifié
        K->>K: Charger plugin
    else Hashes différents
        S-->>K: ❌ Tampering détecté
        K->>K: ❌ Refuser chargement
    end
```

---

## 4. Bonnes Pratiques pour les Développeurs

### Checklist de Sécurité

```mermaid
flowchart LR
    subgraph Do["✅ À Faire"]
        D1[Sandboxed par défaut]
        D2[Permissions minimales]
        D3[Valider inputs]
        D4[Pas d'état local]
        D5[Signer en prod]
    end
    
    subgraph Dont["❌ À Éviter"]
        A1[Trusted sans besoin]
        A2[Permissions larges]
        A3[Inputs non validés]
        A4[État dans le plugin]
        A5[Code non signé]
    end
    
    Do -.->|Au lieu de| Dont
    
    style Do fill:#E8F5E9,stroke:#388E3C
    style Dont fill:#FFEBEE,stroke:#C62828
```

### 1. Utiliser le Sandboxing par Défaut

```yaml
# ✅ RECOMMANDÉ: Sandboxed pour isolation maximale
execution_mode: sandboxed

# ⚠️ UNIQUEMENT SI NÉCESSAIRE: Trusted pour accès kernel
execution_mode: trusted
# Nécessite: accès FastAPI hooks, objets kernel complexes
```

### 2. Demander des Permissions Minimales

```yaml
# ❌ TROP LARGE
permissions:
  - resource: "db.*"
    actions: ["*"]
    effect: allow

# ✅ MINIMAL
permissions:
  - resource: "db.main.users"
    actions: ["read"]
    effect: allow
  - resource: "db.main.posts"
    actions: ["read", "write"]
    effect: allow
```

### 3. Valider Tous les Inputs

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok
from pydantic import BaseModel, Field

# ✅ Schema de validation
class GreetInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    language: str = Field(default="fr")

class Plugin(AutoDispatchMixin, TrustedBase):
    
    @action("greet")
    async def greet(self, payload: dict):
        # Valider l'input
        try:
            validated = GreetInput(**payload)
        except ValidationError as e:
            return error(msg=str(e), code="invalid_input")
        
        return ok(message=f"Bonjour, {validated.name} !")
```

### 4. Pas d'État Local

```python
# ❌ MAUVAIS: État dans le plugin
class Plugin(TrustedBase):
    def __init__(self):
        self.cache_local = {}  # ⚠️ Perdu au reload !

# ✅ BON: État dans les services
class Plugin(TrustedBase):
    async def on_load(self):
        self.cache = self.get_service("cache")  # ✅ Persistant
    
    async def store(self, key, value):
        await self.cache.set(key, value)  # ✅ Sauvegardé
```

### 5. Signer en Production

```bash
# Développement
# Pas de signature requise

# Production (strict_trusted activé)
xcore plugin sign plugins/my_plugin/

# Vérifier
xcore plugin validate plugins/my_plugin/
```

---

## 5. matrice de Sécurité

### Comparaison Trusted vs Sandboxed

| Caractéristique | Trusted | Sandboxed |
| :--- | :--- | :--- |
| **Processus** | Principal | Isolé (OS) |
| **Performance** | ⚡ Rapide | 🐌 IPC overhead |
| **Isolation** | 🔶 Logique | 🔒 Physique |
| **Accès Kernel** | ✅ Complet | ❌ Via IPC uniquement |
| **AST Scan** | ⚠️ Partiel | ✅ Complet |
| **Usage** | Dev / Confiance | Prod / Tiers |

### Tableau des Permissions par Défaut

| Action | Trusted | Sandboxed |
| :--- | :--- | :--- |
| Appeler autre plugin | ✅ (avec permission) | ✅ (avec permission) |
| Accéder DB publique | ✅ | ✅ |
| Accéder DB privée | ❌ | ❌ |
| Modifier kernel | ❌ | ❌ |
| Import restreint | ⚠️ (whitelist) | ❌ (bloqué AST) |
| Route HTTP | ✅ | ✅ (via IPC) |

---

## Prochaines Lectures

| 📚 Guide | Objectif |
| :--- | :--- |
| [Event System](events.md) | Messagerie sécurisée |
| [Plugin Creation](creating-plugins.md) | Développer des plugins |
| [Troubleshooting](troubleshooting.md) | Déboguer les erreurs |
