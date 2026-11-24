"""
service.py — Service `keys` : une clé de chiffrement par organisation, et une rotation (#312).

Un moteur qui scelle ses secrets avec UNE clé de processus les met tous dans le même
panier : dans un produit multi-organisation, la fuite de cette clé est la fuite des
mots de passe SMTP/IMAP de tous les clients, et il n'existe aucun chemin de rotation.

Ce service rend à chaque organisation SA clé, par usage, dérivée d'une clé maîtresse :

    keys = self.get_service("keys")

    key = keys.data_key(purpose="doctype.password")      # tenant courant, version courante
    stored = keys.tag(key.version, encrypt(key.key, secret))       # "v3:<chiffré>"

    version, ciphertext = keys.split(stored)             # relire, quelle que soit la version
    secret = decrypt(keys.data_key(purpose="doctype.password", version=version).key, ciphertext)

    await keys.rotate("acme")                            # nouvelle version + réécriture

Ce que le service fait, et ne fait pas :

  * **Dérivation** — HKDF-SHA256 (RFC 5869) sur la clé maîtresse, avec l'organisation,
    l'usage et la version dans `info`. Deux organisations, deux usages ou deux versions
    ne partagent jamais une clé, et connaître l'une n'apprend rien des autres.
  * **Version** — un entier par organisation, exposé pour que le porteur d'un secret
    range `v<n>:<chiffré>` et qu'une rotation puisse relire l'ancien.
  * **Rotation** — `rotate(tenant)` ouvre une nouvelle version puis appelle les
    réécritures enregistrées par les plugins (`on_rotate`) : chacun relit ses secrets
    sous l'ancienne version et les rescelle sous la nouvelle.
  * **Il ne chiffre pas.** Il rend 32 octets ; l'algorithme (Fernet, AES-GCM…) reste
    au porteur du secret, qui en connaît le format. `DataKey.urlsafe()` donne la forme
    attendue par Fernet.

La clé maîtresse vient de la configuration (`services.keys.master_key`, à lire dans une
variable d'environnement) ; un coffre externe (KMS, Vault) se branche en fournissant un
`KeyProvider` — voir `HKDFKeyProvider`, qui est l'implémentation par défaut.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import inspect
import re
import weakref
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Protocol

from ...kernel.observability import get_logger
from ..base import BaseService, ServiceStatus
from .store import KeyVersion, MemoryVersionStore, VersionConflict, VersionStore

if TYPE_CHECKING:
    from ...configurations.sections import KeysConfig

logger = get_logger("xcore.services.keys")

KEY_BYTES = 32
MIN_MASTER_KEY_BYTES = 32
_TAG_RE = re.compile(r"^v(\d+):(.*)$", re.DOTALL)

RotationHandler = Callable[[str, int, int], Awaitable[Any] | Any]


class KeyServiceError(Exception):
    """Configuration ou usage invalide du service de clés."""


class UnknownKeyVersion(KeyServiceError):
    """Version de clé demandée inconnue pour cette organisation."""


@dataclass(frozen=True)
class DataKey:
    """Une clé de chiffrement d'organisation, pour un usage et une version."""

    tenant_id: str
    purpose: str
    version: int
    key: bytes = field(repr=False)  # jamais dans un log ni une trace

    def urlsafe(self) -> bytes:
        """La clé en base64 URL-safe (32 octets) — la forme qu'attend `Fernet(...)`."""
        return base64.urlsafe_b64encode(self.key)


@dataclass
class RotationResult:
    """Ce qu'une rotation a fait : versions, et le sort de chaque réécriture."""

    tenant_id: str
    old_version: int
    new_version: int
    # nom de la réécriture → "ok" ou le message de l'erreur
    handlers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(outcome == "ok" for outcome in self.handlers.values())


# ── Fournisseur de clés ──────────────────────────────────────────────────────


class KeyProvider(Protocol):
    """D'où vient une clé de données. Défaut : dérivation HKDF ; un KMS s'y substitue."""

    @property
    def current_master_id(self) -> int:
        """Identifiant de la clé maîtresse sous laquelle ouvrir une nouvelle version."""

    def derive(
        self, master_id: int, tenant_id: str, purpose: str, version: int
    ) -> bytes:
        """Rend les 32 octets de la clé de données."""


def hkdf_sha256(
    key: bytes, info: bytes, length: int = KEY_BYTES, salt: bytes = b""
) -> bytes:
    """HKDF-SHA256 (RFC 5869), extraction puis expansion — bibliothèque standard seule."""
    if length > 255 * hashlib.sha256().digest_size:
        raise ValueError("longueur HKDF trop grande")
    prk = hmac.new(salt or b"\x00" * 32, key, hashlib.sha256).digest()
    output, block, counter = b"", b"", 1
    while len(output) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        output += block
        counter += 1
    return output[:length]


def _field(value: str) -> bytes:
    """Champ préfixé par sa longueur : `("a", "bc")` et `("ab", "c")` ne se confondent pas."""
    raw = value.encode("utf-8")
    return len(raw).to_bytes(4, "big") + raw


class HKDFKeyProvider:
    """
    Clés dérivées d'une ou plusieurs clés maîtresses numérotées.

    Plusieurs clés maîtresses = rotation de la clé maîtresse elle-même : la plus haute
    numérotée sert aux NOUVELLES versions, les autres restent pour relire l'existant.
    Ne jamais retirer une clé maîtresse tant qu'un secret scellé sous elle subsiste.
    """

    _SALT = b"xcore.services.keys/v1"

    def __init__(self, master_keys: dict[int, bytes]) -> None:
        if not master_keys:
            raise KeyServiceError("aucune clé maîtresse configurée")
        for master_id, key in master_keys.items():
            if master_id < 1:
                raise KeyServiceError(
                    "un identifiant de clé maîtresse est un entier ≥ 1"
                )
            if len(key) < MIN_MASTER_KEY_BYTES:
                raise KeyServiceError(
                    f"clé maîtresse {master_id} trop courte ({len(key)} octets) : "
                    f"{MIN_MASTER_KEY_BYTES} au minimum — "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
        self._master_keys = dict(master_keys)

    @property
    def current_master_id(self) -> int:
        return max(self._master_keys)

    @property
    def oldest_master_id(self) -> int:
        return min(self._master_keys)

    def has(self, master_id: int) -> bool:
        return master_id in self._master_keys

    def derive(
        self, master_id: int, tenant_id: str, purpose: str, version: int
    ) -> bytes:
        master = self._master_keys.get(master_id)
        if master is None:
            raise KeyServiceError(
                f"la clé maîtresse {master_id} n'est plus configurée : impossible de "
                f"relire la version {version} de l'organisation {tenant_id!r}"
            )
        info = (
            b"xcore:data-key"
            + _field(tenant_id)
            + _field(purpose)
            + _field(str(version))
        )
        return hkdf_sha256(master, info, KEY_BYTES, self._SALT)


def _parse_master_keys(config: "KeysConfig") -> dict[int, bytes]:
    def _bytes(value: Any) -> bytes:
        return value if isinstance(value, bytes) else str(value).encode("utf-8")

    keys: dict[int, bytes] = {}
    for master_id, value in (getattr(config, "master_keys", None) or {}).items():
        try:
            keys[int(master_id)] = _bytes(value)
        except (TypeError, ValueError) as e:
            raise KeyServiceError(
                f"services.keys.master_keys : identifiant {master_id!r} non entier"
            ) from e
    if single := getattr(config, "master_key", None):
        if 1 in keys:
            raise KeyServiceError(
                "services.keys : master_key est la clé n°1 — ne pas la répéter dans master_keys"
            )
        keys[1] = _bytes(single)
    return keys


# ── Service ──────────────────────────────────────────────────────────────────


class KeyService(BaseService):
    name = "keys"

    def __init__(
        self,
        config: "KeysConfig | None" = None,
        *,
        provider: KeyProvider | None = None,
        store: VersionStore | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._provider = provider
        self._store: VersionStore = store or MemoryVersionStore()
        # organisation → versions connues (triées) ; relu depuis le store.
        self._versions: dict[str, list[KeyVersion]] = {}
        self._handlers: dict[str, Any] = {}
        self._refresher: asyncio.Task | None = None
        self._rotation_lock = asyncio.Lock()

    # ── Cycle de vie ──────────────────────────────────────────

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        if self._provider is None:
            if self._config is None:
                raise KeyServiceError("KeyService : ni configuration ni KeyProvider")
            self._provider = HKDFKeyProvider(_parse_master_keys(self._config))
        await self._store.setup()
        await self.refresh()
        interval = float(getattr(self._config, "refresh_seconds", 0) or 0)
        if interval > 0 and self._store.shared:
            self._refresher = asyncio.create_task(self._refresh_loop(interval))
        self._status = ServiceStatus.READY
        if not self._store.durable:
            logger.warning(
                "keys: versions gardées en mémoire — une rotation sera perdue au redémarrage",
                hint="services.keys.store: database (ou file) en production",
            )
        logger.info(
            "key service ready",
            store=type(self._store).__name__,
            master_key_id=self._provider.current_master_id,
            tenants=len(self._versions),
        )

    async def _refresh_loop(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await self.refresh()
            except Exception as e:  # noqa: BLE001 - on garde les versions déjà connues
                logger.warning("key versions refresh failed", error=str(e))

    async def refresh(self) -> None:
        """Relit les versions depuis le store (une rotation faite par un autre worker)."""
        self._versions = await self._store.load()

    async def shutdown(self) -> None:
        if self._refresher is not None:
            self._refresher.cancel()
            await asyncio.gather(self._refresher, return_exceptions=True)
            self._refresher = None
        self._handlers.clear()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        if self._provider is None:
            return False, "key service not initialized"
        try:
            self._provider.derive(
                self._provider.current_master_id, "health", "check", 1
            )
        except Exception as e:  # noqa: BLE001
            return False, str(e)
        return True, "ok"

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "store": type(self._store).__name__,
            "durable": self._store.durable,
            "master_key_id": getattr(self._provider, "current_master_id", None),
            "tenants": len(self._versions),
            "rotation_handlers": sorted(self._handlers),
        }

    # ── Clés ──────────────────────────────────────────────────

    def _provider_or_raise(self) -> KeyProvider:
        if self._provider is None:
            raise KeyServiceError("key service not initialized")
        return self._provider

    @staticmethod
    def _tenant(tenant_id: str | None) -> str:
        if tenant_id is None:
            from ...kernel.tenancy.services import _current_tenant_id

            tenant_id = _current_tenant_id.get()
        if not isinstance(tenant_id, str) or not tenant_id:
            raise KeyServiceError("tenant_id vide")
        return tenant_id

    def _implicit_first(self, tenant_id: str) -> KeyVersion:
        """
        Version 1 d'une organisation qui n'a jamais tourné : rien n'est écrit, elle est
        dérivée sous la PLUS ANCIENNE clé maîtresse — ajouter une clé maîtresse ne change
        donc pas les clés déjà en service.
        """
        provider = self._provider_or_raise()
        master_id = getattr(provider, "oldest_master_id", provider.current_master_id)
        return KeyVersion(tenant_id=tenant_id, version=1, master_id=master_id)

    def _known(self, tenant_id: str) -> list[KeyVersion]:
        return self._versions.get(tenant_id) or [self._implicit_first(tenant_id)]

    def current_version(self, tenant_id: str | None = None) -> int:
        """Version de clé sous laquelle sceller MAINTENANT pour cette organisation."""
        return self._known(self._tenant(tenant_id))[-1].version

    def versions(self, tenant_id: str | None = None) -> list[int]:
        return [v.version for v in self._known(self._tenant(tenant_id))]

    def data_key(
        self,
        tenant_id: str | None = None,
        purpose: str = "default",
        *,
        version: int | None = None,
    ) -> DataKey:
        """
        Clé de chiffrement de l'organisation pour `purpose`.

        `tenant_id=None` : l'organisation de la requête en cours (ContextVar tenant).
        `version=None`   : la version courante (pour sceller) ; une version précise pour
        relire un secret rangé `v<n>:…`.
        """
        tenant = self._tenant(tenant_id)
        if not isinstance(purpose, str) or not purpose:
            raise KeyServiceError("purpose vide")
        known = self._known(tenant)
        if version is None:
            record = known[-1]
        else:
            record = next((v for v in known if v.version == version), None)
            if record is None:
                raise UnknownKeyVersion(
                    f"version {version} inconnue pour l'organisation {tenant!r} "
                    f"(connues : {[v.version for v in known]})"
                )
        key = self._provider_or_raise().derive(
            record.master_id, tenant, purpose, record.version
        )
        return DataKey(
            tenant_id=tenant, purpose=purpose, version=record.version, key=key
        )

    # ── Format `v<n>:<chiffré>` ───────────────────────────────

    @staticmethod
    def tag(version: int, ciphertext: str) -> str:
        """Range la version avec le chiffré : `tag(3, "gAAAA…")` → `"v3:gAAAA…"`."""
        return f"v{int(version)}:{ciphertext}"

    @staticmethod
    def split(stored: str) -> tuple[int | None, str]:
        """
        `"v3:gAAAA…"` → `(3, "gAAAA…")`. Une valeur sans préfixe rend `(None, valeur)` :
        un secret scellé AVANT ce service, à relire avec l'ancienne clé du porteur.
        """
        match = _TAG_RE.match(stored)
        if match is None:
            return None, stored
        return int(match.group(1)), match.group(2)

    def is_current(self, stored: str, tenant_id: str | None = None) -> bool:
        """Vrai si `stored` est scellé sous la version courante (rien à réécrire)."""
        version, _ = self.split(stored)
        return version == self.current_version(tenant_id)

    # ── Rotation ──────────────────────────────────────────────

    def on_rotate(self, name: str, handler: RotationHandler) -> None:
        """
        Enregistre une réécriture : `handler(tenant_id, old_version, new_version)`.

        Appelée par `rotate()` ; elle relit les secrets de l'organisation sous
        `old_version` (et toute version antérieure) et les rescelle sous `new_version`.
        Une méthode de plugin est tenue par référence FAIBLE : un plugin déchargé n'est
        pas épinglé en mémoire, et sa réécriture disparaît avec lui.
        """
        if inspect.ismethod(handler):
            self._handlers[name] = weakref.WeakMethod(handler)
        else:
            self._handlers[name] = handler

    def off_rotate(self, name: str) -> None:
        self._handlers.pop(name, None)

    def _live_handlers(self) -> dict[str, RotationHandler]:
        live: dict[str, RotationHandler] = {}
        for name, handler in list(self._handlers.items()):
            if isinstance(handler, weakref.WeakMethod):
                handler = handler()
                if handler is None:  # plugin déchargé
                    del self._handlers[name]
                    continue
            live[name] = handler
        return live

    async def rotate(self, tenant_id: str | None = None) -> RotationResult:
        """
        Ouvre une nouvelle version de clé pour l'organisation, puis lance les réécritures.

        La nouvelle version est durable AVANT la première réécriture, et les anciennes
        restent dérivables : une réécriture qui échoue ne perd rien, elle laisse des
        secrets sous l'ancienne version (`RotationResult.handlers` dit lesquelles) et
        peut être relancée avec `reseal()`.
        """
        tenant = self._tenant(tenant_id)
        provider = self._provider_or_raise()
        async with self._rotation_lock:
            await self.refresh()  # un autre worker a peut-être déjà tourné
            known = self._known(tenant)
            old = known[-1]
            new = KeyVersion(
                tenant_id=tenant,
                version=old.version + 1,
                master_id=provider.current_master_id,
            )
            try:
                if tenant not in self._versions:
                    # Première rotation : inscrire la version 1 implicite, pour qu'elle
                    # garde SA clé maîtresse quoi qu'il arrive ensuite à la configuration.
                    await self._store.append(old)
                await self._store.append(new)
            except VersionConflict:
                # Un autre worker vient d'ouvrir cette version : c'est lui qui lance
                # les réécritures. Tourner une seconde fois ferait deux versions.
                await self.refresh()
                logger.info(
                    "key already rotated by another worker",
                    tenant=tenant,
                    version=self._known(tenant)[-1].version,
                )
                return RotationResult(
                    tenant_id=tenant,
                    old_version=old.version,
                    new_version=self._known(tenant)[-1].version,
                )
            await self.refresh()
        logger.info(
            "key rotated",
            tenant=tenant,
            old_version=old.version,
            new_version=new.version,
            master_key_id=new.master_id,
        )
        return await self._run_handlers(tenant, old.version, new.version)

    async def reseal(self, tenant_id: str | None = None) -> RotationResult:
        """Relance les réécritures vers la version courante, sans ouvrir de version."""
        tenant = self._tenant(tenant_id)
        known = self._known(tenant)
        old = known[-2].version if len(known) > 1 else known[-1].version
        return await self._run_handlers(tenant, old, known[-1].version)

    async def _run_handlers(self, tenant: str, old: int, new: int) -> RotationResult:
        result = RotationResult(tenant_id=tenant, old_version=old, new_version=new)
        for name, handler in self._live_handlers().items():
            try:
                outcome = handler(tenant, old, new)
                if inspect.isawaitable(outcome):
                    await outcome
                result.handlers[name] = "ok"
            except (
                Exception
            ) as e:  # noqa: BLE001 - une réécriture ne bloque pas les autres
                result.handlers[name] = str(e) or type(e).__name__
                logger.error(
                    "key rotation handler failed",
                    tenant=tenant,
                    handler=name,
                    error=str(e),
                    hint="secrets left under the old version; retry with keys.reseal()",
                )
        return result

    async def rotate_stale(
        self, tenants: list[str] | None = None
    ) -> list[RotationResult]:
        """
        Après l'ajout d'une clé maîtresse : fait tourner chaque organisation dont la
        version courante dépend encore d'une clé maîtresse plus ancienne.

        `tenants` : organisations à considérer en plus de celles que le store connaît
        (une organisation qui n'a jamais tourné n'y figure pas).
        """
        provider = self._provider_or_raise()
        await self.refresh()
        results = []
        for tenant in sorted(set(self._versions) | set(tenants or [])):
            if self._known(tenant)[-1].master_id != provider.current_master_id:
                results.append(await self.rotate(tenant))
        return results
