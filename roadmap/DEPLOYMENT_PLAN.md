# Architecture de déploiement XCore — `.xdeploy` & `xcore-agent`

> Document de synthèse — artefact de distribution chiffré, gestion des clés, résolution des secrets côté client.
> Dernière mise à jour : 2026-08-10

---

## Partie I — Architecture

### 1. Vue d'ensemble

```text
┌─────────────────────────────────────────────────┐
│                   XCORE HUB                     │
│                                                 │
│ Marketplace │ Projects │ Registry │ Deployment │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
      XDevKeys     Build Engine   Artifact Store
          │            │             │
          └────────────┼─────────────┘
                       │
                  encrypted
                  .xdeploy
                       │
                       ▼
                ┌─────────────┐
                │  VPS Client │
                │             │
                │ xcore-agent │
                └──────┬──────┘
                       │
                 decrypt/install
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
           Plugin A Plugin B Plugin C
```

**Principe directeur du système entier :**

> Le Hub construit et distribue du code chiffré. Le VPS client génère, détient et consomme les secrets. Ces deux responsabilités ne doivent jamais se croiser sur le même canal de confiance.

### 5 composants

| Composant | Rôle |
|---|---|
| **XCore Hub** | Marketplace, gestion de projets, build engine, registre d'artefacts |
| **XDevKeys** | Identité — authentifie *qui* parle au Hub |
| **`.xdeploy`** | Unité de distribution — artefact chiffré et signé, lié à un projet |
| **Chiffrement + signature** | Confidentialité (AES-GCM) + intégrité/provenance (signature du manifeste) |
| **xcore-agent** | Composant côté VPS qui télécharge, vérifie, déchiffre, installe |

### 2. Distinction fondamentale : authentification vs autorisation

- **XDevKey** → authentifie le *projet/l'agent* auprès du Hub (identité).
- **Deployment Key (DEK enveloppée)** → autorise le déchiffrement du *contenu* d'un artefact précis (accès à la ressource).

Ne jamais fusionner ces deux mécanismes. Un XDevKey compromis ne doit jamais, à lui seul, permettre d'exfiltrer le contenu d'un artefact client.

### 3. Format `.xdeploy`

#### Structure avant chiffrement

```text
xdeploy/
├── manifest.json
├── integration.yaml
│
├── plugins/
│   ├── auth/
│   │   ├── plugin.yaml
│   │   ├── .env.template
│   │   └── artifact
│   ├── database/
│   │   ├── plugin.yaml
│   │   ├── .env.template
│   │   └── artifact
│   └── stock/
│       ├── plugin.yaml
│       ├── .env.template
│       └── artifact
│
└── deployment/
    └── install.yaml
```

#### Pipeline de packaging

```text
PACKAGE → TAR/ZIP → COMPRESS → ENCRYPT → SIGN → .xdeploy.enc
```

#### `install.yaml` — whitelist d'actions, jamais un DSL arbitraire

**Règle non négociable** : `install.yaml` ne doit jamais permettre d'exécuter des commandes shell arbitraires. Sinon l'artefact chiffré devient un cheval de Troie signé.

```yaml
version: "1"
deployment:
  steps:
    - id: prepare
      action: prepare
    - id: database
      action: provision
      plugin: xcore.database
    - id: auth
      action: install
      plugin: xcore.auth
    - id: configure
      action: configure
    - id: start
      action: start
    - id: healthcheck
      action: healthcheck
```

**Actions autorisées (whitelist fermée) :**
```
prepare · download · extract · install_plugin · configure_plugin
write_env · start · stop · restart · healthcheck · rollback
```

**Jamais autorisé :**
```yaml
action: exec
command: "..."   # ← à bannir structurellement
```

> Cohérence interne : ce modèle réutilise la même philosophie que `ASTScanner` et `FilesystemGuard` déjà présents dans le kernel xcore — whitelist stricte plutôt que blacklist, fail-closed par défaut.

### 4. Gestion des clés — chiffrement par enveloppe

#### Pourquoi une enveloppe et pas un secret partagé

Un secret statique partagé entre Hub et tous les agents ne permet ni révocation fine ni traçabilité. Le modèle d'enveloppe (un DEK par artefact, chiffré individuellement pour chaque agent autorisé) résout les deux problèmes.

#### 4.1 Enrôlement de l'agent (une fois, à l'installation du VPS)

```text
xcore-agent (VPS)                          XCore Hub
      │                                          │
      │ 1. Génère localement agent_priv/agent_pub │
      │    agent_priv ne quitte JAMAIS le VPS     │
      │                                          │
      │──── 2. Enrollment request ──────────────▶│
      │      { project_id, agent_pub,            │
      │        vps_fingerprint, xdevkey }        │
      │                                          │
      │◀──── 3. Enrollment ack ──────────────────│
      │      { agent_id, enrolled: true }         │
```

Le Hub enregistre uniquement `agent_pub` dans son registre. `agent_priv` reste sur le VPS, idéalement dans un TPM/HSM logiciel, ou a minima en `0600` root-only.

#### 4.2 À chaque déploiement (Build Engine)

```text
1. DEK = random(32 bytes)                     # clé symétrique unique par artefact
2. artifact.enc = AES-256-GCM(DEK, xdeploy_tar)  # chiffrement authentifié (AEAD)
3. Pour chaque agent autorisé :
     wrapped_keys[agent_id] = RSA-OAEP(agent_pub, DEK)
4. manifest.json = {
     artifact_hash: sha256(artifact.enc),
     signature: Sign(hub_signing_key, artifact.enc),
     wrapped_keys: { agent_01JABC: "...", agent_01JXYZ: "..." }
   }
```

**Le Hub ne conserve jamais le DEK en clair après l'étape 3.**

#### 4.3 Côté agent — ordre des opérations critique

```text
1. Télécharge artifact.enc + manifest.json

2. VÉRIFIE LA SIGNATURE AVANT TOUT LE RESTE
     verify(hub_pub_key, artifact.enc, manifest.signature)
     → échec = ABORT immédiat, rien n'est extrait

3. DEK = RSA-OAEP-decrypt(agent_priv, wrapped_keys[son_agent_id])

4. xdeploy_tar = AES-GCM-decrypt(DEK, artifact.enc)
     → le tag AEAD échoue si la donnée a été altérée → ABORT

5. DEK utilisée en mémoire uniquement, jamais écrite sur disque, purgée après usage
```

> ⚠️ Point de sécurité clé : **vérifier signature → puis déchiffrer**, jamais l'inverse (pattern "verify-then-decrypt", pas "decrypt-then-verify"). Sinon l'agent traite un blob non authentifié pendant l'extraction (surface d'attaque : zip-bomb, path traversal).

#### 4.4 Révocation

Comme chaque agent a sa propre `wrapped_key`, révoquer un VPS compromis = ne plus envelopper le DEK pour cet `agent_id` sur les **futures** releases. Pas besoin de régénérer tout le système de clés. Si compromission avérée : invalider `agent_id` côté Hub + déclencher rotation complète des secrets applicatifs sur ce VPS.

### 5. Résolution des secrets — vue d'ensemble

#### Catégories de variables dans `.env.template`

```yaml
# plugins/stock/.env.template
environment:
  required:
    - STOCK_DATABASE_URL
    - STOCK_API_KEY
  optional:
    - STOCK_LOG_LEVEL
  generated:              # auto-générés, jamais demandés à l'humain
    - STOCK_INTERNAL_TOKEN
```

| Catégorie | Origine de la valeur |
|---|---|
| `required` | Fournie par le client — humain, PaaS, ou secrets backend |
| `optional` | Valeur par défaut si absente |
| `generated` | Générée localement par l'agent (`os.urandom`), jamais transmise nulle part |

#### Stockage local sur le VPS

```text
/etc/xcore/projects/my-erp/
├── project.env                  # 0600
├── plugins/
│   ├── auth.env                 # 0600
│   ├── database.env             # 0600
│   └── stock.env                # 0600
└── .keys/
    └── agent_private.pem        # 0600, jamais lu par autre chose que l'agent
```

**Règles impératives :**
- Permissions `0600`, compte système dédié (pas root si évitable).
- Jamais dans les logs — liste explicite de patterns sensibles (`*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`) à masquer systématiquement dans tout output.
- Injection uniquement dans l'environnement du process du plugin concerné (`env=` au subprocess), jamais dans l'environnement global du shell de déploiement.
- Chiffrement au repos si le threat model l'exige (`age`, `systemd-creds`, clé dérivée du TPM machine).

### 6. Trois stratégies de résolution des secrets

#### A. Prompt interactif (déploiement manuel uniquement)

Valable **uniquement** lors du premier provisioning humain (`xcore-agent init`), jamais dans une boucle de déploiement automatisée.

```text
xcore-agent init my-erp
  → prompt local sur le VPS (jamais via le Hub), input masqué
  → écrit dans /etc/xcore/projects/my-erp/plugins/stock.env
  → renvoie au Hub uniquement { configured: true }, jamais la valeur
```

#### B. Vault côté client (le plus robuste)

```yaml
# project.env
secrets_backend: vault
vault:
  addr: https://vault.client-internal:8200
  path_prefix: secret/xcore/my-erp/
```

L'agent résout chaque variable directement contre le Vault du client, en local, sans jamais transiter par XCore Hub.

#### C. Vault hébergé côté Hub (SaaS géré)

Acceptable si bien isolé — voir section 7.

#### D. PaaS headless (Dockploy, Coolify, CapRover, K8s, CI/CD)

**Le prompt interactif casse totalement dans ce contexte** — pas de TTY, process headless, déclenché par webhook.

```python
# Lecture depuis l'environnement du process — compatible avec tout PaaS
def resolve_secret(key: str, required: bool = True) -> str | None:
    value = os.environ.get(key)
    if value is None and required:
        raise DeploymentError(
            f"Variable '{key}' manquante. Configurez-la dans les "
            f"Environment Variables de votre plateforme avant de "
            f"relancer le déploiement."
        )
    return value
```

L'agent délègue la collecte à la plateforme (Dockploy UI, K8s Secrets, CI secrets) et se contente de **lire et valider** — c'est le plus petit dénominateur commun compatible avec tout orchestrateur.

### 7. Vault hébergé côté Hub — si tu choisis cette option

#### Changement de modèle de menace

| | Vault côté client | Vault côté Hub |
|---|---|---|
| Hub compromis | Aucun secret applicatif exposé | Risque de fuite centralisée multi-tenant |
| Confort client | Configuration requise | Zéro-config |

Ce n'est pas intrinsèquement mauvais — dépend du profil client (auto-hébergés exigeants vs PME zéro-config). Si retenu, appliquer strictement :

#### Règles impératives

1. **Isolation stricte par projet** — un `path` et une `policy` Vault par `project_id`, jamais de token admin global utilisé en routine.

2. **L'agent parle DIRECTEMENT à Vault, jamais via l'API applicative du Hub.**
   ```
   xcore-agent → (mTLS, cert = agent_priv) → Vault
   ```
   Ne jamais faire transiter par `hub_api → vault → hub_api → agent` : les logs applicatifs, l'APM, les middlewares de logging peuvent accidentellement capturer un secret en transit. C'est la cause n°1 de fuite dans ce type d'architecture.

3. **Authentification via mTLS avec `agent_priv` déjà enrôlé** (section 4.1) — pas de nouveau système de credentials séparé. Token Vault éphémère (TTL court, ex. 15 min), jamais de token statique stocké sur le VPS.

4. **Audit logging Vault activé** — traçabilité `agent_id / timestamp / projet / clé lue` (jamais la valeur).

5. **Auto-unseal via KMS** (AWS KMS, GCP KMS, HashiCorp Cloud) — jamais de clés de unseal partagées manuellement.

#### Modèle hybride recommandé

```yaml
secrets_backend: hub_vault   # ou "client_vault" ou "prompt"
hub_vault:
  auth_method: cert          # utilise agent_priv existant
```

Permet d'offrir le confort managé tout en gardant l'option "rien ne sort de mon infra" pour les clients à exigences strictes (banque, santé), sans maintenir deux architectures séparées — juste un backend interchangeable au niveau de l'agent.

### 8. Séquence complète de `xcore-agent`

```text
authenticate (XDevKey + project_id)
      │
      ▼
request artifact → download encrypted artifact
      │
      ▼
VERIFY SIGNATURE (avant tout déchiffrement)
      │
      ▼
unwrap DEK (RSA-OAEP avec agent_priv)
      │
      ▼
decrypt artifact (AES-GCM, vérifie intégrité)
      │
      ▼
verify manifest/hash décrypté
      │
      ▼
extract → validate project → resolve install sequence
      │
      ▼
resolve_secret() pour chaque variable required
  ├── manquante → FAIL FAST, message clair, PAS de prompt bloquant
  └── présente → continue
      │
      ▼
install plugins → apply plugin.yaml → apply environment
      │
      ▼
start services → healthcheck
      │
      ▼
notify XCore Hub (statut auto-déclaré — voir limite ci-dessous)
```

#### Limite du reporting de statut

Le JSON de notification envoyé au Hub est **auto-déclaré par l'agent**. Un agent compromis peut mentir sur le statut. Si ce statut sert à des décisions sensibles (facturation, alerting), prévoir une vérification indépendante côté Hub (ex. healthcheck HTTP effectué par le Hub lui-même vers un endpoint exposé par le VPS) plutôt qu'une confiance aveugle dans l'auto-déclaration.

```json
{
  "project_id": "prj_01JXYZ",
  "deployment_id": "dep_01JABC",
  "status": "success",
  "version": "1.0.0",
  "plugins": [
    { "id": "xcore.auth", "version": "2.1.0", "status": "installed" }
  ]
}
```

### 9. Rotation des secrets — modèle blue/green

```text
xcore-agent rotate-secret --plugin stock --key STOCK_API_KEY
  → nouvelle valeur (prompt ou vault pull, selon backend configuré)
  → écrit .env.new
  → redémarre le plugin avec le nouveau .env
  → healthcheck OK  → remplace l'ancien .env
  → healthcheck KO  → rollback automatique sur l'ancien .env
```

Même logique que pour les artefacts eux-mêmes — cohérent avec l'action `rollback` déjà whitelistée dans `install.yaml`.

**Piège spécifique aux PaaS type Dockploy/Coolify** : les secrets `generated` (ex. `STOCK_INTERNAL_TOKEN`) doivent être écrits dans un **volume persistant**, pas dans le système de fichiers éphémère du conteneur — sinon chaque redéploiement régénère un nouveau token et casse silencieusement les intégrations qui en dépendaient.

### 10. Tableau récapitulatif — stratégie selon le contexte de déploiement

| Contexte | Stratégie de résolution des secrets |
|---|---|
| `xcore-agent init` en SSH manuel (premier déploiement) | Prompt interactif |
| Dockploy / Coolify / CapRover (webhook, headless) | Lecture depuis env vars injectées par la plateforme |
| Kubernetes | Secrets K8s montés en env ou volume |
| CI/CD (GitHub Actions → deploy) | Secrets du pipeline CI |
| Vault (client ou Hub) | Résolution dynamique via auth mTLS agent, jamais de prompt |

### 11. Ce qui ne doit JAMAIS transiter par XCore Hub

- `agent_private_key`
- Le DEK en clair (uniquement sous forme enveloppée par clé publique agent)
- Les valeurs de secrets applicatifs réels (`.env` en clair)

**Ce que XCore Hub peut légitimement voir/stocker**

- `artifact.enc` (chiffré, inerte sans DEK)
- `wrapped_keys` (DEK chiffrées individuellement par agent)
- Les **noms** de variables requises (`.env.template`), jamais les valeurs
- Le statut de déploiement auto-déclaré (à corroborer si utilisé pour des décisions sensibles)

### 12. Checklist d'implémentation

- [ ] Génération de paire de clés par agent à l'enrôlement, `agent_priv` jamais transmise
- [ ] Chiffrement AES-256-GCM (AEAD) du contenu, DEK unique par artefact
- [ ] Enveloppement du DEK par RSA-OAEP (ou ECIES) pour chaque agent autorisé
- [ ] Signature du manifeste (Ed25519 recommandé) vérifiée **avant** déchiffrement
- [ ] `install.yaml` limité à une whitelist fermée d'actions, aucun `exec` arbitraire
- [ ] `.env.template` déclaratif — `required` / `optional` / `generated`
- [ ] Résolution des secrets via `os.environ` en mode headless (compatible tout PaaS)
- [ ] Prompt interactif réservé strictement à `init`, jamais dans `deploy`
- [ ] Permissions `0600` sur tous les fichiers `.env` et clés privées
- [ ] Masquage systématique des patterns sensibles dans tous les logs
- [ ] Volume persistant pour les secrets `generated` (survie aux redéploiements)
- [ ] Révocation par retrait de `wrapped_keys[agent_id]`, sans regénération globale
- [ ] Rotation blue/green avec rollback automatique sur healthcheck échoué
- [ ] (Si Vault Hub) agent → Vault en mTLS direct, jamais via l'API applicative du Hub
- [ ] (Si Vault Hub) audit logging + auto-unseal KMS activés

---

## Partie II — Plan d'implémentation

### Décisions cadrées

- **Approche** : implémentation par phases, MVP = agent complet y compris secrets.
- **Dépendance crypto** : ajout de `cryptography` (AES-GCM, RSA-OAEP, Ed25519). Le repo n'utilise actuellement que de la crypto stdlib (HMAC).
- **Emplacement du code** : à trancher (repo `xcore` vs nouveau repo `xcore-agent`). Le plan isole les frontières pour permettre un split tardif sans refonte.
- **État existant** : signature HMAC-SHA256 à secret partagé (`xcore/kernel/security/signature.py`), `ASTScanner`/`ManifestValidator`/`FilesystemGuard`, `DependencyResolver` (vagues topologiques), `PluginLoader` (`load_all`/`reload`), `PluginManifest` via xcoresdk (champs `env`, `extra`). Rien pour le déploiement — greenfield.
- **Coexistence** : le HMAC `plugin.sig` reste pour le mode trusted local ; le nouveau schéma Ed25519/AES-GCM/RSA-OAEP est dédié à la distribution.

### Structure cible

```
xcore/deployment/
├── crypto.py        # lib PARTAGÉE (hub build engine + agent) : AES-GCM, RSA-OAEP, Ed25519, verify-then-decrypt
├── format.py        # lib PARTAGÉE : schéma manifest.json, structure tar .xdeploy
├── builder.py       # hub-side : pipeline PACKAGE → TAR → COMPRESS → ENCRYPT → SIGN
├── actions.py       # agent : whitelist fermée des actions install.yaml
├── sequencer.py     # agent : moteur d'exécution de la séquence
└── agent/
    ├── enroll.py    # génération paires de clés, enrôlement, stockage hub_pub
    ├── deploy.py    # séquence complète §8 (auth → download → verify → unwrap → decrypt → install)
    ├── secrets.py   # résolveurs env/prompt/vault + generated + masquage logs
    └── rotate.py    # rotation blue/green + rollback
```

Frontières de transférabilité :
- `crypto.py` + `format.py` → transférables telles quelles dans un autre repo.
- `builder.py` → candidat futur Hub SaaS (build engine).
- `agent/` → candidat futur repo `xcore-agent`.

### Phase 0 — Fondations

1. `poetry add cryptography`
2. Créer le package `xcore/deployment/` avec les frontières ci-dessus
3. Section de config `deployment:` dans `integration.yaml` (backend secrets, project_id, endpoints)

### Phase 1 — Format `.xdeploy` + crypto (lib partagée)

- `crypto.py` :
  - `AES-256-GCM` avec DEK unique par artefact (AEAD, tag vérifié)
  - `RSA-OAEP` (wrap DEK par `agent_pub` de chaque agent autorisé → `wrapped_keys`)
  - `Ed25519` (signature du manifeste, `hub_pub` embarqué à l'enrôlement)
  - **verify-then-decrypt** : ordre imposé, jamais l'inverse
- `format.py` : schéma `manifest.json` (artifact_hash, signature, wrapped_keys, version) + structure tar (`manifest.json`, `integration.yaml`, `plugins/*/{plugin.yaml,.env.template,artifact}`, `deployment/install.yaml`)
- `builder.py` : `PACKAGE → TAR/GZIP → ENCRYPT → SIGN → .xdeploy.enc`
- Le DEK jamais persisté côté hub après l'étape 3 de l'enveloppe

### Phase 2 — Moteur install.yaml (whitelist fermée)

- Parseur + validateur fail-closed : **aucun `exec`/commande arbitraire**, whitelist = `prepare · download · extract · install_plugin · configure_plugin · write_env · start · stop · restart · healthcheck · rollback`
- Extraction sûre : `FilesystemGuard` réutilisé (anti path-traversal, anti zip-bomb, taille max)
- `install_plugin` via `ManifestValidator` + `DependencyResolver` (ordre de vagues existant) + `PluginLoader`
- `write_env` : écriture `0600` dans `/etc/xcore/projects/<project_id>/plugins/<name>.env`
- `rollback` : retour à l'état précédent (artefact précédent + `.env` précédent)

### Phase 3 — Agent complet y compris secrets (MVP)

- `enroll.py` : génération `agent_priv/pub` locale (priv **jamais transmise**, `0600`), request d'enrôlement `{project_id, agent_pub, vps_fingerprint, xdevkey}`, stockage `hub_pub`
- `deploy.py` : séquence complète du §8 — authenticate (XDevKey) → download → **verify signature** → unwrap DEK (RSA-OAEP) → decrypt (AES-GCM) → verify hash → extract → validate → resolve secrets → install → start → healthcheck → notify Hub (statut auto-déclaré)
- `secrets.py` :
  - Résolveur par catégorie : `required` (env vars du process PaaS / prompt **réservé à `init`** / Vault), `optional` (défaut), `generated` (`os.urandom`, jamais transmis)
  - **Fail-fast** sur variable manquante, message clair, jamais de prompt bloquant en `deploy`
  - Masquage des patterns sensibles (`*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`) dans tous les logs
  - Vault client + Vault Hub (mTLS avec `agent_priv`, TTL court, interface commune → backends interchangeables, Vault mocké en tests)
  - Persistance des `generated` en volume persistant (piège PaaS : survie aux redéploiements)
- `rotate.py` : blue/green `.env.new` → restart → healthcheck → swap ou **rollback automatique**
- Révocation : retrait de `wrapped_keys[agent_id]` (pas de regénération globale)

### Phase 4 — CLI, config, docs

- CLI via `xcli` (ou `python -m xcore.deployment`, selon la décision d'emplacement) : `agent enroll|deploy|rotate-secret|status`
- Section `deployment:` dans `integration.yaml` (backend secrets, project_id, etc.)
- Docs mkdocs `doc/deployment/` (repris de ce document + guide agent) + CHANGELOG 2.4.0 + ROADMAP (V3 Distribution, XCore Hub)

### Tests & vérification

- **Unit** : vecteurs crypto, round-trip builder/verifier, altération détectée (signature, tag AEAD, wrong-agent unwrap), whitelist reject (`action: exec`), résolution secrets (env/prompt/vault mockés), rotation avec rollback
- **Integration** : build d'un artefact depuis un projet fixture → install dans un dossier temp → boot via `PluginLoader`
- **Sécurité** : bandit (pre-commit existant), coverage ≥ 80 (`fail_under` déjà en place), revue du masquage des logs

### Hors périmètre (jalons suivants)

- Hub SaaS complet (marketplace API, build engine web, XDevKeys backend) — ce repo n'en contient que le **builder partagé**
- Vault Hub réel (l'interface est prête, le backend est côté Hub)

### Points à trancher au moment de l'implémentation

1. **Repo du code** : ce repo vs `xcore-agent` séparé — aucune incidence sur les Phases 1-2 grâce aux frontières
2. **Vault client** : intégration réelle au MVP ou interface + mock (recommandé : interface + mock pour le MVP, la lib `hvac` peut attendre)
3. **Notification de statut** au Hub : endpoint réel ou callback configurable
