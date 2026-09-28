# 🛡️ Analyse dynamique de sécurité — Sandbox XCore

**Date :** 28 septembre 2026
**Auteur :** Claude (assistant, session courante)
**Version testée :** XCore v2.7.0 (`chore/dependency-extras`)
**Méthode :** analyse **dynamique** — pas de relecture de code seule. Deux plugins `sandboxed` réels ont été écrits et exécutés dans un vrai process xcore (`Xcore().boot()`, sans mock), en tentant les techniques d'évasion sandbox Python connues. Environnement de test isolé (`/tmp/.../scratchpad/sandbox_dynamic_test/`), jamais commité au dépôt.

---

## 📋 1. Synthèse

Le sandbox XCore repose sur 4 couches documentées (`doc/security/security.md`) : validation du manifeste, scan AST statique, `FilesystemGuard` runtime, signature HMAC (plugins trusted uniquement). Cette analyse dynamique confirme que 3 de ces couches fonctionnent bien en pratique (filesystem, limite mémoire, blocage des imports obfusqués de modules **listés**) — mais révèle **3 techniques d'évasion sandbox fonctionnelles**, toutes confirmées par exécution réelle, qui permettent à un plugin `sandboxed` malveillant d'exécuter des commandes arbitraires sur la machine hôte en contournant totalement l'isolation.

**Racine commune** : le sandbox applicatif Python bloque des **modules par nom**, vérifiés au moment de l'import. Il a trois angles morts structurels :
- des modules qui donnent un accès système équivalent à `os` sans jamais y figurer (`asyncio.subprocess`, `posix`) ;
- des classes système **déjà chargées en mémoire** au démarrage de l'interpréteur (avant même que le guard ne s'installe), accessibles via l'arbre d'héritage Python (`__subclasses__()`) sans jamais passer par un `import` ;
- une désynchronisation entre la liste du scanner statique (54 entrées) et celle du guard runtime (36 entrées).

> **Mise à jour du 28 septembre 2026, même session** : les 3 vulnérabilités du §2 sont **corrigées** dans `xcore/kernel/sandbox/worker.py` (`pwd`/`grp`/`posix` ajoutés à `_FORBIDDEN_MODULES`, blocage direct de `subprocess.Popen.__init__`/`os.fork`/`os.execve`/famille `spawn*`/`asyncio.create_subprocess_exec`/`_shell` — piste de remédiation #3 du §6, la plus robuste). Les 3 PoC ont été ré-exécutés après correction : les trois sont désormais bloqués (`PermissionError: [sandbox] ... interdit dans le sandbox`), voir §8. Un usage légitime d'`asyncio` sans subprocess (`asyncio.sleep`) a été vérifié comme non affecté. Suite de tests complète (1539/1540, seul échec préexistant sans rapport) verte après correctif.

---

## 🔴 2. Vulnérabilités confirmées (exécution réelle)

### #1 — `asyncio.create_subprocess_exec`/`_shell` : exécution de commande arbitraire
**Sévérité : Critique — ✅ Corrigé (voir §8)**

`asyncio` n'apparaît dans **aucune** des deux listes de modules interdits (`DEFAULT_FORBIDDEN` du scanner statique, `_FORBIDDEN_MODULES` du guard runtime — `xcore/kernel/security/section.py` / `xcore/kernel/sandbox/worker.py`). Un plugin sandboxé peut donc faire :

```python
import asyncio
proc = await asyncio.create_subprocess_exec("id", stdout=-1)
out, _ = await proc.communicate()
```

**Résultat obtenu en conditions réelles** :
```json
{"status": "VULNERABLE", "output": "uid=1000(users) gid=1000(users) groups=1000(users),9537(lib23),9558(docker),998(wheel)\n"}
```
Le plugin a exécuté `id` sur la machine hôte et lu sa sortie — accès complet à n'importe quel binaire (`sh -c "..."` via `create_subprocess_shell` a été testé avec le même résultat).

### #2 — `().__class__.__bases__[0].__subclasses__()` → classe `Popen` : évasion classique Python
**Sévérité : Critique — ✅ Corrigé (voir §8)**

Le scanner AST statique bloque bien l'écriture **littérale** de `__subclasses__`/`__globals__`/`__class__` dans le code source (`FORBIDDEN_ATTRIBUTES`, `xcore/kernel/security/section.py:26-37`). Mais ces noms peuvent être construits dynamiquement à l'exécution (`operator.attrgetter("__" + "subclasses" + "__")`), invisibles pour une analyse par nœud AST. En remontant l'arbre d'héritage depuis n'importe quel objet, on retrouve `subprocess.Popen` — déjà chargé en mémoire par l'interpréteur avant même que le plugin ne démarre, donc jamais intercepté par le guard d'import :

```python
base = attrgetter("__class__")(()).__bases__[0]
popen_cls = next(c for c in attrgetter("__subclasses__")(base)() if c.__name__ == "Popen")
p = popen_cls(["id"], stdout=-1)
```

**Résultat obtenu** : `{"status": "VULNERABLE", "output": "uid=1000(users)...\n"}` — identique à #1, sans jamais faire `import subprocess` ni `import asyncio`.

**Note méthodologique** : ce vecteur a nécessité de contourner deux faux positifs sympathiques du scanner (documentés en §4) avant d'atteindre le vrai test — un nom de variable local `imp` a été détecté comme le module `imp`, et `asyncio.subprocess.PIPE` a été détecté comme un accès au module `subprocess` via son nom d'attribut.

### #3 — `import posix` (dynamique) : contournement du blocage de `os`
**Sévérité : Critique — ✅ Corrigé (voir §8)**

`pwd`, `grp` et `posix` figurent dans la liste du scanner statique (`DEFAULT_FORBIDDEN`) mais **pas** dans celle du guard runtime (`_FORBIDDEN_MODULES`) — écart découvert en comparant programmatiquement les deux sets (54 vs 36 entrées, diff ci-dessous). `posix` est le module bas niveau sur lequel `os` est construit sur Unix ; il expose `fork`, `execve`, `kill`, etc. — un accès système quasi identique à `os`, jamais bloqué au runtime :

```python
mod = dynamic_import("posix")
pid = mod.fork()
```

**Résultat obtenu** : `{"status": "VULNERABLE", "forked_pid": 556255, "wait_status": 0}` — fork réussi, process enfant créé sur l'hôte.

**Diff exact des deux listes** (`DEFAULT_FORBIDDEN - _FORBIDDEN_MODULES`, modules réels seulement, hors builtins comme `eval`/`exec` qui sont gérés séparément par `FORBIDDEN_BUILTINS`) : `grp`, `posix`, `pwd`.

---

## ✅ 3. Protections confirmées efficaces (contrôles positifs)

| Protection | Test effectué | Résultat |
|---|---|---|
| `FilesystemGuard` — lecture hors `allowed_paths` | `open("/etc/passwd")` | `PermissionError: [sandbox] open('/etc/passwd') interdit` |
| `FilesystemGuard` — traversée de répertoire | `open("../../../tmp/xcore_sandbox_escape_test.txt", "w")` | Bloqué, même résultat |
| `FilesystemGuard` — écriture autorisée | `open("data/ok.txt", "w")` | `ok_as_expected` — pas de faux positif |
| Guard runtime — import obfusqué de module **listé** | `__import__` construit dynamiquement pour `os`/`ctypes` (contournant le scan statique) | `PermissionError: [sandbox] __import__('os') interdit` — le guard vérifie le **nom résolu**, pas le texte source |
| Limite mémoire (`RLIMIT_DATA`+`RLIMIT_RSS`, `worker.py::_apply_resource_limits`) | Allocation de 2M dicts avec limite à 50MB | `MemoryError` immédiate — **efficace**, contrairement à l'hypothèse initiale que `RLIMIT_RSS` serait un no-op sur Linux moderne (vérifiée fausse par test isolé) |
| `PermissionEngine` IPC (deny-by-default) | Appel sans `permissions:` déclarées dans `plugin.yaml` | Refusé avant même d'atteindre le sandbox — bonne défense en profondeur en amont |
| Scanner AST statique | `import os` littéral dans un plugin sandboxed | Chargement refusé (`scan failed`), le worker ne démarre même pas |

---

## ⚠️ 4. Constats secondaires

- **Le scanner statique est plus agressif que documenté** — il bloque un nom de **variable locale** coïncidant avec un nom de module interdit (`imp = ...` a été détecté comme le module `imp`), et un **attribut** dont le nom correspond à un module interdit même sur un objet légitime (`asyncio.subprocess.PIPE` détecté via `.subprocess`). Ce n'est pas un défaut de sécurité (fail-closed), mais une source probable de faux positifs frustrants pour des auteurs de plugins légitimes — à documenter dans `doc/security/security.md`.
- **`MemoryLimiter` (`xcore/kernel/sandbox/isolation.py:55-73`, `RLIMIT_AS`) est du code mort** — jamais appelé nulle part dans le runtime (`grep` confirmé). La vraie limite appliquée est `worker.py::_apply_resource_limits()` (`RLIMIT_DATA`+`RLIMIT_RSS`), qui s'avère efficace empiriquement mais duplique une seconde implémentation jamais utilisée.
- **Une bombe mémoire tue le worker entier**, pas seulement l'action en cours — le process sandboxé crashe (`EOF inattendu sur stdout`), déclenchant `_handle_crash()`/le mécanisme de retry. Comportement sûr au niveau isolation (le process malveillant meurt), mais pas gracieux au niveau applicatif (toute requête en vol sur ce worker échoue, pas seulement celle qui a déclenché la bombe).

---

## 🧭 5. Limite structurelle à documenter clairement

Le sandbox XCore est un **sandbox applicatif en pur Python**, dans le même process/espace mémoire que l'interpréteur hôte. Cette catégorie de sandbox a une limite fondamentale, indépendante de la qualité de l'implémentation : *tout objet système déjà chargé en mémoire par l'interpréteur reste atteignable par introspection* (technique `__subclasses__()`, connue et documentée depuis des années dans la communauté sécurité Python — ce n'est pas une découverte originale de cette analyse, mais sa confirmation empirique contre XCore l'est).

`doc/security/security.md` présente actuellement le sandbox sans cette réserve. Recommandation : ajouter une section "Limites connues" explicite — le sandbox protège contre des plugins tiers **négligents ou peu sophistiqués**, pas contre un attaquant qui connaît les techniques classiques d'évasion. Pour une isolation réellement étanche contre un adversaire actif, il faudrait un sandboxing niveau OS en complément (namespaces Linux, seccomp-bpf, gVisor, conteneur dédié par plugin) — hors scope d'un correctif de code.

---

## 🔧 6. Pistes de remédiation (non implémentées — à discuter)

| # | Fix | Effort | Couvre |
|---|---|---|---|
| 1 | Ajouter `pwd`, `grp`, `posix` à `_FORBIDDEN_MODULES` (`worker.py`) | Trivial | #3 entièrement |
| 2 | Patcher spécifiquement `asyncio.subprocess.create_subprocess_exec`/`_shell`/`create_subprocess_transport` dans `FilesystemGuard._install_impl()` (le module `asyncio` lui-même doit rester utilisable — c'est le runtime du worker) | Faible | #1 |
| 3 | Patcher `subprocess.Popen.__init__` et `os.posix_spawn`/`os.fork`/`os.execve` directement (bloquer l'**exécution**, pas seulement l'**import**) — robuste même via `__subclasses__()` puisque la classe elle-même refuse d'agir | Moyen | #1, #2, #3 en une seule couche, plus robuste que des correctifs au cas par cas |
| 4 | Documenter la limite structurelle en §5 dans `doc/security/security.md` | Trivial | Communication/attentes, pas un fix technique |
| 5 | (Plus lourd, hors scope immédiat) Sandboxing niveau OS pour les déploiements à forte exigence d'isolation | Élevé | Seule vraie garantie contre un attaquant sophistiqué |

Item 3 est la remédiation la plus robuste : elle ferme #1/#2/#3 par un seul mécanisme (bloquer au niveau de l'appel système réel, pas de la résolution de nom de module), et résiste par construction à toute future variante du même contournement.

---

## 📌 7. Recommandation process

Le rapport `technical_debt_remediation_verification_2026-08-11.md` recommandait déjà de revérifier tout rapport d'audit contre le code avant d'en faire un ticket. Ici c'est l'inverse qui s'est produit et qui vaut d'être noté : **l'hypothèse initiale sur `RLIMIT_RSS` (théoriquement un no-op sur Linux moderne) s'est révélée fausse à l'exécution** — la seule façon de le savoir était de tester, pas de lire le code. Les 3 vulnérabilités listées en §2, à l'inverse, semblaient improbables en lisant seulement les 36 entrées de `_FORBIDDEN_MODULES` (une liste qui semble complète) — ce n'est qu'en les exécutant réellement contre le vrai worker qu'elles se sont confirmées. Aucune des deux conclusions n'était devinable de manière fiable depuis la seule lecture statique.

---

## ✅ 8. Vérification post-correctif

Correctif appliqué dans `xcore/kernel/sandbox/worker.py` (item 1 + 2 simplifié + 3 du tableau §6, fusionnés en une seule couche) :
- `pwd`, `grp`, `posix` ajoutés à `_FORBIDDEN_MODULES` — ferme #3 au niveau import.
- Nouvelle « Couche 5 » dans `FilesystemGuard._install_impl()` : patch direct des objets déjà chargés en mémoire plutôt que du seul mécanisme d'import — `subprocess.Popen.__init__`, `subprocess.call`/`run`/`check_call`/`check_output`, toute la famille `os.fork`/`os.exec*`/`os.spawn*`/`os.posix_spawn*`/`os.system`/`os.popen`, et `asyncio.create_subprocess_exec`/`_shell` (module et sous-module `asyncio.subprocess`). Approche volontairement plus large que le strict minimum demandé par #1/#3 : elle ferme aussi #2 (`__subclasses__()` → `Popen`), qu'un simple ajout à la liste de modules interdits n'aurait pas pu fermer puisqu'aucun `import` n'y est jamais exécuté.

**Les 3 PoC du §2 ré-exécutés après correctif** :

```json
{
  "try_asyncio_subprocess":     {"status": "blocked", "error": "PermissionError: [sandbox] asyncio.create_subprocess_exec/_shell() interdit dans le sandbox"},
  "try_subclasses_popen_exec":  {"status": "blocked", "error": "PermissionError: [sandbox] subprocess.Popen() interdit dans le sandbox"},
  "try_posix_system":           {"status": "blocked", "error": "PermissionError: [sandbox] __import__('posix') interdit dans le sandbox"}
}
```

**Non-régression vérifiée** :
- Usage légitime d'`asyncio` sans subprocess (`await asyncio.sleep(0.05)`) : toujours fonctionnel — `{"status": "ok_as_expected"}`.
- `FilesystemGuard` (lecture/écriture) : comportement inchangé.
- Suite de tests complète du projet : `1539 passed, 1 skipped` (le seul échec, `test_router_construit`, est le bug Studio préexistant sans rapport, déjà documenté ailleurs).

**Ce qui reste ouvert** : le constat structurel du §5 (sandbox purement applicatif Python, limite fondamentale face à un attaquant qui découvrirait une *nouvelle* classe système exploitable déjà chargée) et l'item 4 du §6 (documenter cette limite dans `doc/security/security.md`) ne sont pas traités par ce correctif — celui-ci ferme les 3 vecteurs concrets trouvés, pas la catégorie de risque dans l'absolu.
