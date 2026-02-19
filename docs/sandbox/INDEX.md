# Module Sandbox

Le module `xcore/sandbox` est le cœur du runtime plugins moderne de xcore.

## Fichiers racine et sous-modules

```{toctree}
:maxdepth: 2

manager
router
contracts/INDEX
sandbox/INDEX
trusted/INDEX
tools/INDEX
```

## Flux global

1. Lecture manifeste plugin
2. Activation trusted/sandboxed
3. Application rate limit + retry
4. Exposition via API routeur plugin

## Contribution

- Conserver les garanties de sécurité (signature, scanner, quotas).
- Tester systématiquement trusted et sandboxed après tout changement.
