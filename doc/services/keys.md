---
title: Keys Service
description: One encryption key per organisation, derived from a master key, with versions and rotation.
icon: material/key-chain
---

# Keys Service

The `keys` service hands every organisation (tenant) **its own** encryption key, per purpose, derived from a master key. A leaked key exposes one organisation, not all of them, and keys can be rotated.

The service **does not encrypt**: it returns 32 bytes. The cipher (Fernet, AES-GCM…) stays with the code that owns the secret.

---

### Usage

```python linenums="1"
keys = self.get_service("keys")

# Seal — current tenant, current version
key = keys.data_key(purpose="doctype.password")
stored = keys.tag(key.version, encrypt(key.key, secret))      # "v3:<ciphertext>"

# Read — whatever version the secret was sealed under
version, ciphertext = keys.split(stored)
key = keys.data_key(purpose="doctype.password", version=version)
secret = decrypt(key.key, ciphertext)
```

`tenant_id` defaults to the tenant of the current request. `DataKey.urlsafe()` returns the base64 form expected by `Fernet(...)`. `keys.split()` returns `(None, value)` for a value without a `v<n>:` prefix — a secret sealed before this service existed.

Keys are derived with HKDF-SHA256 (RFC 5869); tenant, purpose and version are all part of the derivation, so two organisations, two purposes or two versions never share a key.

---

### Rotation

```python linenums="1"
class Plugin(TrustedBase):
    async def on_load(self):
        self.keys = self.get_service("keys")
        self.keys.on_rotate("mail.settings", self.reseal)   # held by weak reference

    async def reseal(self, tenant_id: str, old_version: int, new_version: int):
        ...  # read each secret with its stored version, seal it again with data_key()

result = await keys.rotate("acme")     # opens version n+1, then runs the handlers
result.handlers                        # {"mail.settings": "ok"}
```

- The new version is durable **before** any handler runs and old versions stay derivable: a failing handler loses nothing. Retry with `await keys.reseal(tenant)`.
- `keys.is_current(stored)` tells whether a stored secret still needs rewriting.
- **Rotating the master key**: add the next one under `master_keys` (`{2: ...}`) *without removing the first*. Versions already in service keep their master key; `await keys.rotate_stale(tenants=[...])` moves organisations to the new one. Never remove a master key while a secret sealed under it remains.

---

### YAML Configuration

```yaml linenums="1" title="integration.yaml"
services:
  keys:
    enabled: true                       # default: false
    master_key: ${XCORE_MASTER_KEY}     # ≥ 32 bytes — never in the repository
    # master_keys: {2: "${XCORE_MASTER_KEY_2}"}
    store: database                     # memory | file (default) | database
    path: .xcore/key_versions.json      # store: file
    database: ~                         # store: database — null = default connection (db)
    refresh_seconds: 60                 # re-read versions rotated by another worker
```

The store only holds key **versions** (not secret, but they must be durable and shared): `file` suits a single host, `database` several workers. An invalid configuration (key shorter than 32 bytes, `store: database` without a SQL connection) **stops the boot**.

An external vault (KMS, Vault) plugs in by passing a `KeyProvider` to `KeyService`.
