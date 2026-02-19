# signer.py

Le fichier `xcore/sandbox/trusted/signer.py` gère signature et vérification des plugins trusted (HMAC-SHA256).

## API

- `sign_plugin(manifest, secret_key)`
- `verify_plugin(manifest, secret_key)`
- `is_signed(manifest)`

## Mécanisme

- Hash du manifest + tous les fichiers `src/`
- Signature stockée dans `plugin.sig`
- Vérification en comparaison constante (`hmac.compare_digest`)

## Exception

- `SignatureError`

## Contribution

- Toute modification de l’algorithme doit prévoir migration des signatures.
- Ne jamais stocker la clé secrète dans le plugin.
