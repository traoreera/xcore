# 📂 Vérification du Rapport de Dette Technique (XCore)

**Date :** 11 Août 2026
**Auteur :** Claude (assistant, session `telemetry-setup`)
**Framework :** XCore (v2.3.5)
**Référence :** `reports/technical_debt_remediation_2026-08-10.md` (Jules, Ingénieur Principal, 10 Août 2026)
**Périmètre :** Vérification ligne par ligne des 6 points de remédiation du rapport référencé, contre l'état réel du code sur `main` + branche `telemetry-setup`.

---

## 📋 1. Synthèse

Le rapport du 10 août propose 6 actions de remédiation classées par priorité (Haute/Moyenne/Basse). Chaque point a été vérifié individuellement en lisant le code source concerné plutôt qu'en faisant confiance à la description du rapport.

**Résultat : sur 6 points, 3 sont périmés (déjà livrés avant même la date du rapport), 1 est mal posé (contredit l'architecture réelle), et 2 sont réels.**

Ce n'est pas un cas isolé : les rapports `report_analysis.md` et `reports/technical_debt_remediation_2026-08-10.md` produits par le même processus d'audit contenaient déjà, lors de leur revue dans cette session, des constats similaires ne correspondant plus à l'état du code (ex. bug de race condition sur `_load_permissions`, déjà corrigé avant que le rapport ne soit écrit). **Recommandation : tout rapport d'audit généré doit être revérifié contre le code avant d'être transformé en ticket de travail.**

---

## 🔍 2. Vérification détaillée

### #1 — Fast-path EventBus pour handler unique
**Rapport :** Priorité Haute (Effort Faible / Impact Très Élevé) — `emit()` enveloppe systématiquement dans `asyncio.gather` même pour un seul handler.

**Constat réel :** Déjà implémenté. `xcore/kernel/events/bus.py:158` :
```python
if len(matched_handlers) == 1:
    entry = matched_handlers[0]
    ...
```
Le fast-path proposé par le rapport existe déjà, avec la même logique.

**Verdict : ✅ Périmé — aucune action requise.**

---

### #2 — Recyclage du subprocess sandboxé sur timeout IPC
**Rapport :** Priorité Haute (Effort Faible / Impact Élevé) — un canal IPC qui expire (`IPCTimeoutError`) ne déclenche pas de recyclage du subprocess.

**Constat réel :** Confirmé manquant. Dans `xcore/kernel/sandbox/process_manager.py`, la méthode `call()` (ligne 170-183) — le chemin emprunté par **chaque appel plugin réel** — ne catch que `IPCProcessDead` :
```python
try:
    resp = await self._channel.call(action, payload)
    return resp.data
except IPCProcessDead:
    await self._handle_crash()
    raise
```
`IPCTimeoutError` (levée par `ipc.py` quand `readline()` timeout — subprocess bloqué mais pas mort) n'est **pas catchée ici** et remonte telle quelle à l'appelant, sans recyclage. Il existe bien une `_health_loop` périodique qui finira par détecter un ping en timeout et appeler `_handle_crash()`, mais c'est une détection différée (au prochain intervalle de health check), pas une réaction immédiate sur le chemin de la requête utilisateur qui vient d'échouer.

**Verdict : 🔴 Réel — action requise.**

---

### #3 — Désactivation de l'audit sur cache hit (permissions)
**Rapport :** Priorité Haute (Effort Faible / Impact Élevé) — `_audit()` s'exécute même sur cache hit.

**Constat réel :** Partiellement déjà fait. Dans `xcore/kernel/permissions/engine.py:67-81`, un cache hit appelle déjà `_audit(..., emit_event=False)` — l'émission d'événement (la partie la plus coûteuse, `events.emit_sync`) est donc déjà court-circuitée. Il reste cependant un `self._audit_log.append(entry)` inconditionnel (ligne 138) à chaque hit, sans mécanisme pour le désactiver.

**Verdict : 🟡 Réel mais périmètre plus restreint que ce que décrit le rapport — déjà à moitié optimisé.**

---

### #4 — Cache de wrappers multi-tenant
**Rapport :** Priorité Moyenne (Effort Moyen / Impact Élevé) — `wrap_services_for_tenant` serait instancié à chaque requête, sur le chemin critique.

**Constat réel :** Non applicable. `wrap_services_for_tenant` n'est appelé **qu'une seule fois**, au chargement du plugin — `xcore/kernel/runtime/lifecycle.py:178-184` :
```python
if tenancy is not None and tenancy.enabled:
    from ...kernel.tenancy.services import wrap_services_for_tenant
    ctx.services = wrap_services_for_tenant(...)
```
Le tenant courant est résolu dynamiquement à l'intérieur des wrappers déjà créés, via un `ContextVar` (`_current_tenant_id`, mis à jour par requête dans `supervisor._dispatch`). Il n'y a donc pas d'instanciation par requête à mettre en cache — le design actuel (un seul jeu de wrappers partagé, lecture dynamique du tenant) est déjà plus efficace que la solution proposée par le rapport (un jeu de wrappers par tenant_id, qui multiplierait les objets sans bénéfice).

**Verdict : ⚪ Périmé / mal posé — aucune action, le rapport ne correspond pas à l'architecture réelle.**

---

### #5 — Durcissement ASTScanner (`__subclasses__`, `__globals__`, `__builtins__`)
**Rapport :** Priorité Moyenne (Effort Moyen / Impact Élevé) — ces attributs sensibles ne seraient pas bloqués, ouvrant un risque de sandbox escape.

**Constat réel :** Déjà implémenté. `xcore/kernel/security/section.py:26-37` :
```python
FORBIDDEN_ATTRIBUTES = {
    "__class__", "__globals__", "__subclasses__", "__code__", "__mro__",
    "__builtins__", "__dict__", "__base__", "__bases__", "__getattribute__",
}
```
`sys` est également déjà dans `DEFAULT_FORBIDDEN` (import direct bloqué).

**Verdict : ✅ Périmé — aucune action requise.**

---

### #6 — Nettoyage des bases/fichiers temporaires en CI
**Rapport :** Priorité Basse (Effort Faible / Impact Moyen) — pas de teardown systématique des SQLite temporaires dans les tests.

**Constat réel :** Confirmé manquant. Aucune fixture `autouse` de nettoyage dans `tests/conftest.py`. Risque partiellement réduit par le fait que le fixture DB principal utilise déjà `sqlite:///:memory:` (pas de fichier sur disque), mais d'autres fixtures (`plugins_dir`, `temp_dir`, `fake_plugin_dir`) créent des répertoires temporaires sans garantie de nettoyage systématique en fin de session.

**Verdict : 🟡 Réel, priorité basse — confirmé conforme à la description du rapport.**

---

## 📊 3. Todo de correction — priorisée par version

Cohérent avec la fenêtre de maintenance V2 (patchs jusqu'à décembre 2026, voir `ROADMAP_PROGRESS.md`) :

| Version | Item | Statut | Effort |
| :--- | :--- | :---: | :--- |
| **v2.3.6** | Recyclage du subprocess sandboxé sur `IPCTimeoutError` — catch dans `process_manager.py:call()` en plus de `IPCProcessDead` | 🔴 À faire | Faible |
| **v2.3.6** | Fixture `autouse` de nettoyage DB/temp dans `tests/conftest.py` | 🟡 À faire | Faible |
| **v2.3.7** (optionnel) | Paramètre pour désactiver `_audit_log.append` sur cache hit dans `engine.py` | 🟡 Optionnel | Faible |
| — | Fast-path EventBus | ✅ Déjà livré | — |
| — | Cache de wrappers multi-tenant | ⚪ Non applicable | — |
| — | Durcissement ASTScanner | ✅ Déjà livré | — |

---

## 📌 4. Recommandation process

Avant d'assigner un ticket depuis un rapport d'audit généré automatiquement (`reports/*.md`), vérifier systématiquement l'état réel du code référencé — grep/lecture directe, pas confiance aveugle dans le "Constat". Sur les 3 derniers rapports revus dans cette session (`report_analysis.md`, `SECURITY_AND_PERFORMANCE_REPORT.md`, `technical_debt_remediation_2026-08-10.md`), chacun contenait au moins un constat déjà corrigé au moment de la lecture.
