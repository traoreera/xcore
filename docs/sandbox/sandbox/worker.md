# worker.py

Le fichier `xcore/sandbox/sandbox/worker.py` est le process plugin sandboxed (boucle stdin/stdout JSON).

## Rôle

- Appliquer limite mémoire (`RLIMIT_AS`) si configurée
- Charger le plugin depuis `src/main.py`
- Recevoir requêtes JSON `{action, payload}`
- Exécuter `plugin.handle(...)`
- Retourner une réponse JSON standard

## Contrat I/O

- entrée: une ligne JSON par requête
- sortie: une ligne JSON par réponse

## Contribution

- Garder le worker minimal et robuste.
- Ne pas introduire de dépendances non nécessaires dans ce process critique.
