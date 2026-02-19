# ipc.py

Le fichier `xcore/sandbox/sandbox/ipc.py` implémente un canal JSON newline-delimited entre core et worker.

## API

- `IPCChannel.call(action, payload)`
- `IPCChannel.close()`

## Types

- `IPCResponse`
- `IPCError`
- `IPCTimeoutError`
- `IPCProcessDead`

## Garanties

- Lock async: un appel IPC à la fois par process
- Timeout configurable
- Limite de taille de réponse

## Contribution

- Corriger les exceptions avec `raise ... from e` cohérent.
- Ajouter des tests sur EOF, JSON invalide, timeout, broken pipe.
