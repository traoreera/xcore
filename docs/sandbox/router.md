# router.py

Le fichier `xcore/sandbox/router.py` expose l’API HTTP de gestion et d’appel des plugins.

## Endpoints

- `POST /app/{plugin_name}/{action}`
- `GET /app/status` (protégé par clé API si configurée)
- `POST /app/{plugin_name}/reload` (protégé)
- `POST /app/{plugin_name}/load` (protégé)
- `DELETE /app/{plugin_name}/unload` (protégé)

## Sécurité

- Header: `X-Plugin-Key`
- Validation via `verify_admin_key`
- Si `app.state.plugin_api_key` absent: mode dev (pas de blocage)

## Schémas

- `PluginCallRequest`
- `PluginCallResponse`

## Exemple

```bash
curl -X POST http://localhost:8000/app/demo/ping \
  -H 'Content-Type: application/json' \
  -d '{"payload": {"hello": "world"}}'
```

## Contribution

- Toute route admin doit rester protégée via `verify_admin_key`.
- Conserver des erreurs HTTP explicites (`404`, `401`, `500`).
