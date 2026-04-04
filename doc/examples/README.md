# Exemples XCore

Cette section contient des exemples concrets pour vous aider à démarrer rapidement avec XCore. Chaque exemple est conçu pour illustrer une fonctionnalité spécifique du framework.

---

## 1. Exemples de Plugins

Ces guides pas-à-pas vous montrent comment construire différents types de plugins :

- **[Plugin de Base](basic-plugin.md)** : Structure minimale et point d'entrée `handle()`.
- **[Plugin Complet (CRUD)](complete-plugin.md)** : Utilisation de la base de données, du cache, des routes HTTP et de la validation Pydantic.
- **[Plugin Trusted](trusted-plugin.md)** : Accès total aux services et intégration avancée pour les plugins internes.
- **[Plugin Sandboxed](sandboxed-plugin.md)** : Démonstration de l'isolation de sécurité et du blocage des accès non autorisés (FS Guard, AST).

---

## 2. Exemples de Services

- **[Service de Cache](../guides/services.md#3-service-de-cache-cache)** : Utilisation de Redis et de la mémoire.
- **[Service SQL](../guides/services.md#2-service-de-base-de-donnees-db)** : Pattern Repository et sessions asynchrones.
- **[Service Scheduler](../guides/services.md#4-service-de-planification-scheduler)** : Tâches de fond et jobs Cron.

---

## 3. Guide Pratique : "Créer un plugin de A à Z"

Si vous débutez, nous vous recommandons de suivre le **[Guide de démarrage rapide](../getting-started/quickstart.md)** qui vous accompagne dans la création de votre premier plugin interactif.

---

## 4. Partagez vos Exemples !

Vous avez construit un plugin génial ? Proposez-le à la communauté via une Pull Request sur le dépôt officiel ou publiez-le sur le **[Marketplace XCore](../guides/marketplace.md)**.
