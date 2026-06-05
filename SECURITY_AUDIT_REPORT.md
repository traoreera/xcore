# 🛡️ Rapport d'Audit de Sécurité — XCore Framework

## 1. Résumé Exécutif
XCore est un framework d'orchestration "plugin-first" conçu avec une forte emphase sur la sécurité et l'isolation. L'architecture repose sur un noyau minimaliste et délègue les fonctionnalités à des plugins qui peuvent être exécutés soit en mode **Trusted** (confiance totale, accès direct aux ressources), soit en mode **Sandboxed** (processus isolés avec restrictions strictes).

L'audit révèle une conception robuste, utilisant des techniques de défense en profondeur (AST scanning, monkey-patching, isolation au niveau OS). Les mécanismes de protection contre les vulnérabilités courantes (OWASP) sont bien intégrés, notamment pour le multi-tenancy et la gestion des secrets.

---

## 2. Profil de Menace
L'audit a évalué xcore contre trois vecteurs d'attaque principaux :
1.  **Développeur de Plugin Malveillant (Menace Interne/Tierce) :** Tentative d'évasion de sandbox, vol de données d'autres plugins ou du noyau, déni de service (DoS).
2.  **Attaquant Externe (API) :** Tentative d'accès non autorisé aux actions de plugins, injection SQL, contournement de l'authentification.
3.  **Fuite de données Inter-locataires (Multi-tenancy) :** Accès aux données du locataire B par le locataire A.

---

## 3. Analyse Détaillée des Composants

### 3.1. Sandbox & Isolation (Le cœur du système)
Le système de sandbox utilise une approche multicouche :
-   **Couche 1 : Filesystem Guard** : Monkey-patching de `open`, `os.*` et `pathlib.Path`. Utilise une politique *fail-closed* (tout ce qui n'est pas autorisé est bloqué).
-   **Couche 2 : Exécution Dynamique** : Blocage de `exec()`, `eval()`, `compile()` et `input()` pour empêcher l'exécution de code arbitraire généré à la volée.
-   **Couche 3 : Import Blocking** : Interdiction d'importer des modules sensibles (`os`, `sys`, `subprocess`, `ctypes`, etc.) via un scan AST (C++ ou Python) et un guard au runtime.
-   **Couche 4 : Restrictions de Ressources** : Utilisation de `resource` (Linux) pour limiter la mémoire (RLIMIT_AS) et le temps CPU.
-   **Isolation Disque** : Un `DiskWatcher` surveille en temps réel la taille du répertoire `data/` du plugin.

**Points forts :** L'utilisation d'une extension C++ pour le scan AST offre des performances élevées et une résistance aux contournements par obfuscation simple.
**Risque résiduel :** Sous Windows, les limites de ressources (mémoire/CPU) ne sont pas applicables par le noyau.

### 3.2. Intégrité des Plugins (Signatures)
XCore implémente un système de signatures HMAC-SHA256 pour garantir l'intégrité des plugins **Trusted**.
-   **Vérification Dynamique** : Le hash inclut le manifeste et tous les fichiers sources.
-   **Mode Strict** : Le paramètre `strict_trusted: true` empêche le chargement de tout code non validé.
-   **Anti-Timing Attacks** : Utilisation de `hmac.compare_digest` pour la vérification des signatures et des clés API.

### 3.3. Multi-tenancy & Isolation des Données
L'isolation est gérée via des `ContextVar` asynchrones, garantissant qu'une requête ne peut pas "fuiter" sur le contexte d'une autre.
-   **Base de données** : Utilisation du `search_path` PostgreSQL (schema-based isolation). Une regex stricte valide le `tenant_id` pour prévenir les injections SQL lors du `SET search_path`.
-   **Cache & Scheduler** : Préfixage automatique et transparent des clés/IDs par le `tenant_id`.

### 3.4. Sécurité de l'API & RBAC
-   **Authentification IPC** : Les appels inter-plugins et vers le superviseur sont protégés par une clé API hashée avec PBKDF2 (100 000 itérations par défaut).
-   **Système RBAC** : Dépendances FastAPI `require_role` et `require_permission` extensibles via un plugin d'authentification tierce.

---

## 4. Conformité OWASP Top 10

| Catégorie | État | Implémentation XCore |
| :--- | :--- | :--- |
| **A01:2021-Broken Access Control** | ✅ Robuste | RBAC intégré, isolation multi-tenant stricte, sandbox. |
| **A02:2021-Cryptographic Failures** | ✅ Robuste | PBKDF2 pour les clés, HMAC-SHA256 pour les signatures, stockage sécurisé des hachages. |
| **A03:2021-Injection** | ✅ Robuste | SQLAlchemy text() utilisé partout, validation regex des identifiants de locataires. |
| **A04:2021-Insecure Design** | ✅ Robuste | Architecture fail-closed par défaut. |
| **A05:2021-Security Misconfig** | ⚠️ Attention | CORSMiddleware configuré mais nécessite activation manuelle dans le boot. |
| **A06:2021-Vulnerable Components** | ✅ Géré | Workflow GitHub `security.yml` avec scan de dépendances. |
| **A07:2021-Ident & Auth Failures** | ✅ Robuste | Backend auth interchangeable, protection contre les timing attacks. |
| **A08:2021-Software & Data Integrity** | ✅ Robuste | Signature des plugins Trusted obligatoire en mode strict. |
| **A10:2021-Server-Side Request Forgery** | ✅ Géré | Sandbox bloque les modules réseau (`httpx`, `requests`) par défaut. |

---

## 5. Analyse de l'Environnement & Déploiement
-   **Gestion des Secrets** : XCore valide au démarrage que les clés secrètes ne sont pas celles par défaut (`change-me-in-production`) si `env: production`.
-   **Observabilité** : Logs structurés (JSON possible) permettant un audit précis des actions bloquées par la sandbox.
-   **DevOps** : Dockerfile sécurisé utilisant une image de base à jour et un utilisateur non-root (`vscode`).

---

## 6. Recommandations et Points d'Attention

1.  **CORS** : Bien que présent dans la configuration, assurez-vous d'injecter explicitement le `CORSMiddleware` dans votre application FastAPI si vous l'utilisez comme API publique.
2.  **Windows** : Pour une sécurité maximale en production, utilisez un environnement Linux afin de bénéficier des limites de ressources (cgroups/rlimits).
3.  **Strict Mode** : En production, activez toujours `strict_trusted: true` pour interdire l'exécution de code Trusted non signé.
4.  **C++ Extension** : Compilez l'extension `scanner_core.cpp` pour des performances optimales et une sécurité accrue de l'AST scanner.

---
**Rapport généré par Jules (IA Security Audit Agent)**
