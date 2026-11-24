"""
service.py — Service `outbox` : un effet extérieur APRÈS le commit (#309).

Un hook qui tourne dans une transaction ne peut pas défaire un effet extérieur : le
courriel remis au serveur SMTP pendant la soumission d'un document est parti même si
une écriture suivante échoue — et la re-soumission en envoie un second. Enfiler la
tâche ne règle rien : enfilée dans le hook, elle s'exécute même si la transaction est
annulée ; enfilée après le commit, elle est perdue si le processus meurt entre les deux.

L'outbox passe par la base. On ne fait pas l'effet : on dépose une **intention**, dans
la transaction de l'appelant ; elle est validée ou annulée AVEC le document.

    outbox = self.get_service("outbox")

    async with self.db.session() as session:
        ...                                   # écritures du document
        await outbox.defer(
            "mail", "send", {"to": "a@b.c", "invoice": 42},
            key="invoice:42:submitted",       # idempotent : deux dépôts = un envoi
            session=session,                  # ← la transaction de l'appelant
        )
    # commit  → l'intention existe, le répartiteur appellera mail.send
    # rollback → elle n'a jamais existé

Après le commit, un répartiteur prend les intentions prêtes, appelle la tâche
(`plugin.action`, par le superviseur) et enregistre l'état :

    pending ──ok──▶ sent
       │
       └─échec──▶ pending (attempts+1, prochain essai après un recul exponentiel)
                     └─ max_attempts atteint ──▶ dead   (la file morte)

Garanties, et leur prix :

  * **au moins une fois** — un processus qui meurt après l'envoi mais avant d'écrire
    `sent` fera renvoyer l'intention. La tâche reçoit `payload["_outbox"]` (`id`,
    `key`, `attempt`) pour dédoublonner de son côté ;
  * **un seul répartiteur par intention** — chaque processus réclame une intention par
    une écriture conditionnelle (bail `locked_until`, horloge de la base) ;
  * **même base** — la session passée à `defer` doit être sur la base de l'outbox
    (`services.outbox.database`), sans quoi l'atomicité n'existe pas.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from ...kernel.observability import get_logger
from ..base import BaseService, ServiceStatus
from ..database.sqlexec import (
    FLOAT_TYPE,
    NOW_EPOCH,
    ON_CONFLICT,
    dialect_of,
    engine_of,
    run_statement,
)

if TYPE_CHECKING:
    from ...configurations.sections import OutboxConfig

logger = get_logger("xcore.services.outbox")

TABLE = "xcore_outbox"
PENDING, SENT, DEAD = "pending", "sent", "dead"

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_ERROR_CHARS = 2000

# (plugin, action, payload, tenant_id) → résultat de l'appel
Caller = Callable[[str, str, dict, str], Awaitable[Any]]
Handler = Callable[[dict], Awaitable[Any] | Any]


class OutboxError(Exception):
    """Configuration ou usage invalide de l'outbox."""


@dataclass(frozen=True)
class Receipt:
    """Ce que `defer` a fait. `deferred=False` : cette clé avait déjà été déposée."""

    id: str | None
    deferred: bool


@dataclass(frozen=True)
class Intent:
    """Une intention réclamée par ce répartiteur."""

    id: str
    key: str | None
    plugin: str
    task: str
    payload: dict
    tenant_id: str
    attempts: int


class OutboxService(BaseService):
    name = "outbox"

    def __init__(self, config: "OutboxConfig", adapter: Any) -> None:
        super().__init__()
        self._config = config
        engine = engine_of(adapter)
        dialect = dialect_of(engine)
        if engine is None or dialect is None:
            raise OutboxError("l'outbox demande une base SQL initialisée")
        if dialect not in NOW_EPOCH:
            raise OutboxError(
                f"dialecte {dialect!r} non pris en charge (pris en charge : "
                f"{sorted(NOW_EPOCH)})"
            )
        table = getattr(config, "table", None) or TABLE
        if not _NAME_RE.match(table):
            raise OutboxError(f"nom de table invalide : {table!r}")
        self._engine = engine
        self.dialect = dialect
        self._table_name = table
        self._table = table  # qualifié par le schéma dans init() (PostgreSQL)
        self._owner = uuid.uuid4().hex  # ce répartiteur
        self._caller: Caller | None = None
        self._handlers: dict[str, Handler] = {}
        self._loop_task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._last_purge = 0.0
        self._counts: dict[str, int] = {}
        self._sql: dict[str, str] = {}

    # ── SQL ───────────────────────────────────────────────────

    def _statements(self) -> dict[str, str]:
        t, now, flt = self._table, NOW_EPOCH[self.dialect], FLOAT_TYPE[self.dialect]
        columns = (
            "(id, dedup_key, plugin, task, payload, tenant_id, status, attempts, "
            "next_attempt_at, created_at)"
        )
        values = (
            f"(:id, :key, :plugin, :task, :payload, :tenant_id, '{PENDING}', 0, "
            f"{now} + :delay, {now})"
        )
        if self.dialect in ON_CONFLICT:
            # Pas d'IntegrityError à rattraper : sur PostgreSQL, elle condamnerait la
            # transaction de l'APPELANT — celle qui porte son document.
            insert = (
                f"INSERT INTO {t} {columns} VALUES {values} "
                "ON CONFLICT (dedup_key) DO NOTHING"
            )
        else:
            insert = f"INSERT IGNORE INTO {t} {columns} VALUES {values}"
        free = f"(locked_until IS NULL OR locked_until < {now})"
        return {
            "create": (
                f"CREATE TABLE IF NOT EXISTS {t} ("
                "id VARCHAR(32) NOT NULL PRIMARY KEY, "
                "dedup_key VARCHAR(255) NULL UNIQUE, "
                "plugin VARCHAR(255) NOT NULL, "
                "task VARCHAR(255) NOT NULL, "
                "payload TEXT NOT NULL, "
                "tenant_id VARCHAR(255) NOT NULL, "
                "status VARCHAR(16) NOT NULL, "
                "attempts INTEGER NOT NULL, "
                f"next_attempt_at {flt} NOT NULL, "
                f"created_at {flt} NOT NULL, "
                f"sent_at {flt} NULL, "
                f"locked_until {flt} NULL, "
                "locked_by VARCHAR(32) NULL, "
                "last_error TEXT NULL)"
            ),
            "index": (
                f"CREATE INDEX {self._table_name}_ready "
                f"ON {t} (status, next_attempt_at)"
            ),
            "insert": insert,
            "ready": (
                f"SELECT id FROM {t} WHERE status = '{PENDING}' "
                f"AND next_attempt_at <= {now} AND {free} "
                "ORDER BY next_attempt_at LIMIT :limit"
            ),
            # Réclamation : le bail est pris par l'instruction qui vérifie qu'il est libre.
            "claim": (
                f"UPDATE {t} SET locked_by = :owner, locked_until = {now} + :lease "
                f"WHERE id = :id AND status = '{PENDING}' AND {free}"
            ),
            "fetch": (
                f"SELECT id, dedup_key, plugin, task, payload, tenant_id, attempts "
                f"FROM {t} WHERE id = :id AND locked_by = :owner"
            ),
            "sent": (
                f"UPDATE {t} SET status = '{SENT}', sent_at = {now}, "
                "attempts = attempts + 1, locked_by = NULL, locked_until = NULL, "
                "last_error = NULL WHERE id = :id AND locked_by = :owner"
            ),
            "retry_later": (
                f"UPDATE {t} SET attempts = attempts + 1, "
                f"next_attempt_at = {now} + :delay, last_error = :error, "
                "locked_by = NULL, locked_until = NULL "
                "WHERE id = :id AND locked_by = :owner"
            ),
            "dead": (
                f"UPDATE {t} SET status = '{DEAD}', attempts = attempts + 1, "
                "last_error = :error, locked_by = NULL, locked_until = NULL "
                "WHERE id = :id AND locked_by = :owner"
            ),
            "release": (
                f"UPDATE {t} SET locked_by = NULL, locked_until = NULL "
                "WHERE id = :id AND locked_by = :owner"
            ),
            "revive": (
                f"UPDATE {t} SET status = '{PENDING}', attempts = 0, "
                f"next_attempt_at = {now}, last_error = NULL "
                f"WHERE id = :id AND status = '{DEAD}'"
            ),
            "purge": (
                f"DELETE FROM {t} WHERE status = '{SENT}' AND sent_at < {now} - :age"
            ),
            "counts": f"SELECT status, COUNT(*) FROM {t} GROUP BY status",
            "list": (
                f"SELECT id, dedup_key, plugin, task, tenant_id, status, attempts, "
                f"last_error, created_at FROM {t} WHERE status = :status "
                "ORDER BY created_at LIMIT :limit"
            ),
        }

    async def _run(self, name: str, params: dict | None = None) -> Any:
        return await run_statement(self._engine, self._sql[name], params)

    # ── Cycle de vie ──────────────────────────────────────────

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        if self.dialect == "postgresql":
            # Les sessions d'un plugin sous tenancy ont le `search_path` du tenant : un
            # nom nu n'y trouverait pas la table. On la nomme avec son schéma.
            schema = getattr(self._config, "schema", None)
            if not schema:
                row = (
                    await run_statement(self._engine, "SELECT current_schema()")
                ).first()
                schema = row[0] if row else "public"
            if not _NAME_RE.match(schema):
                raise OutboxError(f"nom de schéma invalide : {schema!r}")
            self._table = f'"{schema}".{self._table_name}'
        self._sql = self._statements()
        try:
            await self._run("create")
        except Exception:
            # Deux processus qui démarrent ensemble : si la table est là, tout va bien.
            await run_statement(
                self._engine, f"SELECT 1 FROM {self._table} WHERE 1 = 0"
            )
        try:
            await self._run("index")
        except Exception:  # noqa: BLE001 - l'index existe déjà
            pass
        self._status = ServiceStatus.READY
        logger.info(
            "outbox ready",
            table=self._table,
            dialect=self.dialect,
            dispatch=self._dispatches,
        )

    @property
    def _dispatches(self) -> bool:
        return bool(getattr(self._config, "dispatch", True))

    def bind(self, caller: Caller) -> None:
        """Branche l'appel des tâches : `caller(plugin, action, payload, tenant_id)`."""
        self._caller = caller

    def register(self, plugin: str, task: str, handler: Handler) -> None:
        """
        Tâche servie par une fonction locale plutôt que par un appel de plugin :
        `handler(payload)`. Prioritaire sur l'appel par le superviseur.
        """
        self._handlers[f"{plugin}.{task}"] = handler

    def unregister(self, plugin: str, task: str) -> None:
        self._handlers.pop(f"{plugin}.{task}", None)

    def start(self) -> None:
        """Démarre le répartiteur (une fois les plugins chargés). Idempotent."""
        if not self._dispatches or self._loop_task is not None:
            return
        self._loop_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        """Arrête le répartiteur — AVANT de décharger les plugins qu'il appelle."""
        task, self._loop_task = self._loop_task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def shutdown(self) -> None:
        await self.stop()
        self._handlers.clear()
        self._caller = None
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            counts = await self.stats()
        except Exception as e:  # noqa: BLE001
            return False, str(e)
        dead = counts.get(DEAD, 0)
        return True, f"ok ({counts.get(PENDING, 0)} pending, {dead} dead)"

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "table": self._table,
            "dispatching": self._loop_task is not None,
            "counts": dict(self._counts),
        }

    # ── Dépôt ─────────────────────────────────────────────────

    async def defer(
        self,
        plugin: str,
        task: str,
        payload: dict | None = None,
        *,
        key: str | None = None,
        session: Any = None,
        delay: float = 0.0,
        tenant_id: str | None = None,
    ) -> Receipt:
        """
        Dépose l'intention d'appeler `plugin.task(payload)` après le commit.

        `session` : la session ou la connexion SQLAlchemy de la transaction en cours
        (asynchrone ou synchrone) — l'intention est validée ou annulée avec elle. Sans
        `session`, l'intention est validée tout de suite, dans sa propre transaction.
        `key` : idempotence — un second dépôt de la même clé ne dépose rien.
        `delay` : secondes à attendre, après le commit, avant le premier essai.
        """
        if not plugin or not task:
            raise OutboxError("defer : plugin et task sont obligatoires")
        if key is not None and (not isinstance(key, str) or not 0 < len(key) <= 255):
            raise OutboxError("defer : key doit être une chaîne de 1 à 255 caractères")
        if tenant_id is None:
            from ...kernel.tenancy.services import _current_tenant_id

            tenant_id = _current_tenant_id.get()
        try:
            body = json.dumps(payload or {}, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Maintenant, dans la transaction — pas dans dix minutes, dans le répartiteur.
            raise OutboxError(f"defer : payload non sérialisable en JSON ({e})") from e

        intent_id = uuid.uuid4().hex
        params = {
            "id": intent_id,
            "key": key,
            "plugin": plugin,
            "task": task,
            "payload": body,
            "tenant_id": tenant_id,
            "delay": max(0.0, float(delay)),
        }
        if session is None:
            result = await self._run("insert", params)
            self.notify()
        else:
            from sqlalchemy import text

            result = session.execute(text(self._sql["insert"]), params)
            if inspect.isawaitable(result):
                result = await result
        if result.rowcount == 0:
            logger.debug(
                "outbox intent already deferred", key=key, task=f"{plugin}.{task}"
            )
            return Receipt(id=None, deferred=False)
        return Receipt(id=intent_id, deferred=True)

    def notify(self) -> None:
        """Réveille le répartiteur sans attendre son prochain tour (après un commit)."""
        self._wake.set()

    # ── Répartiteur ───────────────────────────────────────────

    async def _dispatch_loop(self) -> None:
        poll = max(0.05, float(getattr(self._config, "poll_seconds", 1.0)))
        while True:
            try:
                handled = await self.dispatch_once()
                await self._purge_if_due()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - base injoignable : on réessaiera
                logger.warning("outbox dispatch failed", error=str(e))
                handled = 0
            if handled:
                continue  # il en reste peut-être : pas de pause
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=poll)
            except asyncio.TimeoutError:
                pass

    async def dispatch_once(self) -> int:
        """Traite un lot d'intentions prêtes ; rend le nombre d'intentions traitées."""
        limit = max(1, int(getattr(self._config, "batch_size", 20)))
        rows = (await self._run("ready", {"limit": limit})).all()
        handled = 0
        for (intent_id,) in rows:
            intent = await self._claim(intent_id)
            if intent is None:
                continue  # un autre répartiteur l'a prise
            await self._deliver(intent)
            handled += 1
        return handled

    async def _claim(self, intent_id: str) -> Intent | None:
        lease = float(getattr(self._config, "lease_seconds", 300.0))
        params = {"id": intent_id, "owner": self._owner}
        claimed = await self._run("claim", {**params, "lease": lease})
        if claimed.rowcount != 1:
            return None
        row = (await self._run("fetch", params)).first()
        if row is None:
            return None
        try:
            payload = json.loads(row[4])
        except ValueError:
            payload = {}
        return Intent(
            id=row[0],
            key=row[1],
            plugin=row[2],
            task=row[3],
            payload=payload if isinstance(payload, dict) else {"value": payload},
            tenant_id=row[5],
            attempts=int(row[6]),
        )

    async def _deliver(self, intent: Intent) -> None:
        params = {"id": intent.id, "owner": self._owner}
        attempt = intent.attempts + 1
        try:
            await self._call(intent, attempt)
        except asyncio.CancelledError:
            # Arrêt en plein envoi : on rend l'intention, sans compter d'essai. Elle
            # sera reprise — c'est le « au moins une fois ».
            await asyncio.shield(self._run("release", params))
            raise
        except Exception as e:  # noqa: BLE001 - toute erreur de la tâche est un échec
            await self._record_failure(intent, attempt, e)
            return
        await self._run("sent", params)
        logger.debug(
            "outbox intent sent",
            id=intent.id,
            task=f"{intent.plugin}.{intent.task}",
            attempt=attempt,
        )

    async def _call(self, intent: Intent, attempt: int) -> None:
        payload = {
            **intent.payload,
            "_outbox": {"id": intent.id, "key": intent.key, "attempt": attempt},
        }
        handler = self._handlers.get(f"{intent.plugin}.{intent.task}")
        if handler is not None:
            from ...kernel.tenancy.services import _current_tenant_id

            token = _current_tenant_id.set(intent.tenant_id)
            try:
                result = handler(payload)
                if inspect.isawaitable(result):
                    result = await result
            finally:
                _current_tenant_id.reset(token)
        elif self._caller is not None:
            result = await self._caller(
                intent.plugin, intent.task, payload, intent.tenant_id
            )
        else:
            raise OutboxError(
                f"aucune tâche '{intent.plugin}.{intent.task}' : ni handler enregistré "
                "ni superviseur branché"
            )
        # Un plugin dit son échec par une réponse, pas par une exception.
        if isinstance(result, dict) and result.get("status") == "error":
            raise OutboxError(
                str(result.get("msg") or result.get("code") or "task returned an error")
            )

    async def _record_failure(
        self, intent: Intent, attempt: int, exc: Exception
    ) -> None:
        error = (str(exc) or type(exc).__name__)[:_MAX_ERROR_CHARS]
        params = {"id": intent.id, "owner": self._owner, "error": error}
        max_attempts = max(1, int(getattr(self._config, "max_attempts", 8)))
        fields = {
            "id": intent.id,
            "task": f"{intent.plugin}.{intent.task}",
            "key": intent.key,
            "attempt": attempt,
            "error": error,
        }
        if attempt >= max_attempts:
            await self._run("dead", params)
            logger.error(
                "outbox intent dead, giving up",
                **fields,
                hint="inspect with outbox.list('dead'), requeue with outbox.retry(id)",
            )
            return
        delay = self.backoff(attempt)
        await self._run("retry_later", {**params, "delay": delay})
        logger.warning("outbox intent failed, will retry", **fields, retry_in_s=delay)

    def backoff(self, attempt: int) -> float:
        """Recul exponentiel : base, 2×base, 4×base… plafonné à `max_backoff_seconds`."""
        base = float(getattr(self._config, "backoff_seconds", 5.0))
        ceiling = float(getattr(self._config, "max_backoff_seconds", 3600.0))
        return min(ceiling, base * (2 ** max(0, attempt - 1)))

    async def _purge_if_due(self) -> None:
        age = float(getattr(self._config, "retention_seconds", 0) or 0)
        if age <= 0 or time.monotonic() - self._last_purge < 300:
            return
        self._last_purge = time.monotonic()
        purged = (await self._run("purge", {"age": age})).rowcount
        if purged:
            logger.debug("outbox sent intents purged", count=purged)

    # ── Exploitation ──────────────────────────────────────────

    async def stats(self) -> dict[str, int]:
        """Nombre d'intentions par état : `{"pending": 3, "sent": 120, "dead": 1}`."""
        rows = (await self._run("counts")).all()
        self._counts = {status: int(count) for status, count in rows}
        return dict(self._counts)

    async def list(self, status: str = DEAD, limit: int = 100) -> list[dict]:
        """Intentions dans un état (par défaut : la file morte), les plus anciennes d'abord."""
        rows = (await self._run("list", {"status": status, "limit": int(limit)})).all()
        names = (
            "id",
            "key",
            "plugin",
            "task",
            "tenant_id",
            "status",
            "attempts",
            "last_error",
            "created_at",
        )
        return [dict(zip(names, row)) for row in rows]

    async def retry(self, intent_id: str) -> bool:
        """Remet une intention morte dans la file, compteur d'essais à zéro."""
        revived = (await self._run("revive", {"id": intent_id})).rowcount == 1
        if revived:
            self.notify()
        return revived
