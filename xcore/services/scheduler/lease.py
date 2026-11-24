"""
lease.py — Verrou du scheduler tenu par la BASE (`backend: database`, #317).

Sans verrou, chaque processus qui a enregistré un job l'exécute : deux workers
uvicorn, deux paies. Le verrou Redis règle cela, mais il demande Redis. Ce module
donne la même garantie à qui n'a qu'une base SQL : un **bail** par `job_id`, dans
une table dédiée, que la base tranche.

Choix (ce sont les décisions laissées ouvertes par #317) :

  * **Quelle base ?** `services.scheduler.database` nomme une connexion de
    `services.databases` ; à défaut, la connexion par défaut (`db`). Sans base SQL
    utilisable, le service le dit et passe `DEGRADED` — pas de repli discret.
  * **Quelle table, qui la crée ?** `xcore_scheduler_leases`, créée paresseusement
    à l'initialisation (`CREATE TABLE IF NOT EXISTS`) : trois colonnes, aucune
    migration à livrer ni à oublier.
  * **Quelle horloge ?** Celle de la BASE, dans chaque requête. L'horloge du process
    n'entre dans aucune comparaison : deux machines désynchronisées ne se marchent
    pas dessus.

Protocole (le même que le chemin Redis, `_dispatch_job`) :

  * `acquire` — une écriture conditionnelle atomique : le bail est pris s'il n'existe
    pas ou s'il a expiré. Le premier gagne, les autres passent leur tour.
  * `renew`   — pendant l'exécution, pour qu'un job long ne se fasse pas voler son
    bail ; ne touche que le bail dont on est propriétaire.
  * `release` — ne libère que SON bail (comparaison du jeton), jamais celui d'un
    worker qui l'aurait repris après une expiration.

Une différence voulue avec Redis : `min_hold`. Un job de 10 ms est fini avant que le
second processus — dont le loop avait 50 ms de retard — n'atteigne son déclenchement ;
libéré trop tôt, le bail serait repris et le job rejoué. Le bail est donc gardé au
moins `min_hold` secondes après son acquisition (horloge de la base), le temps que
tous les processus aient vu le même déclenchement.
"""

from __future__ import annotations

import re
from typing import Any

from ...kernel.observability import get_logger
from ..database.sqlexec import dialect_of, engine_of, run_statement

logger = get_logger("xcore.services.scheduler.lease")

TABLE = "xcore_scheduler_leases"

# Horloge de la base, en secondes epoch (flottant), par dialecte.
#   - postgresql : clock_timestamp() et non now(), figé au début de la transaction.
#   - sqlite     : julianday('now') — précision milliseconde, toutes versions.
_NOW = {
    "postgresql": "EXTRACT(EPOCH FROM clock_timestamp())",
    "mysql": "UNIX_TIMESTAMP(NOW(6))",
    "mariadb": "UNIX_TIMESTAMP(NOW(6))",
    "sqlite": "((julianday('now') - 2440587.5) * 86400.0)",
}
_FLOAT = {
    "postgresql": "DOUBLE PRECISION",
    "mysql": "DOUBLE",
    "mariadb": "DOUBLE",
    "sqlite": "REAL",
}
# Dialectes où l'acquisition tient en UNE instruction (upsert conditionnel).
_UPSERT = {"postgresql", "sqlite"}

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LeaseUnavailable(RuntimeError):
    """Le bail en base ne peut pas être mis en place (pas de base SQL, dialecte inconnu)."""


class DatabaseLease:
    """
    Bail par `job_id` dans une table SQL.

    `adapter` est un adaptateur de `services.databases` (`AsyncSQLAdapter` ou
    `SQLAdapter`) : seul son moteur SQLAlchemy est utilisé, chaque opération dans sa
    propre transaction courte — jamais dans celle d'un plugin.
    """

    def __init__(
        self,
        adapter: Any,
        *,
        ttl: float = 300.0,
        min_hold: float = 1.0,
        table: str = TABLE,
    ) -> None:
        engine = engine_of(adapter)
        dialect = dialect_of(engine)
        if engine is None or dialect is None:
            raise LeaseUnavailable(
                "la connexion choisie n'est pas une base SQL initialisée"
            )
        if dialect not in _NOW:
            raise LeaseUnavailable(
                f"dialecte {dialect!r} non pris en charge "
                f"(pris en charge : {sorted(_NOW)})"
            )
        if not _TABLE_NAME_RE.match(table):
            raise LeaseUnavailable(f"nom de table invalide : {table!r}")

        self._engine = engine
        self.dialect = dialect
        self.ttl = float(ttl)
        self.min_hold = max(0.0, float(min_hold))
        self.table = table
        self._now = _NOW[dialect]
        self._sql = self._statements()

    # ── SQL ───────────────────────────────────────────────────

    def _statements(self) -> dict[str, str]:
        t, now = self.table, self._now
        sql = {
            "create": (
                f"CREATE TABLE IF NOT EXISTS {t} ("
                "job_id VARCHAR(255) NOT NULL PRIMARY KEY, "
                "owner VARCHAR(64) NOT NULL, "
                f"acquired_at {_FLOAT[self.dialect]} NOT NULL, "
                f"expires_at {_FLOAT[self.dialect]} NOT NULL)"
            ),
            # Reprise d'un bail EXPIRÉ : la condition est évaluée par la base, sur
            # son horloge, dans l'instruction qui écrit.
            "steal": (
                f"UPDATE {t} SET owner = :owner, acquired_at = {now}, "
                f"expires_at = {now} + :ttl "
                f"WHERE job_id = :job_id AND expires_at < {now}"
            ),
            "renew": (
                f"UPDATE {t} SET expires_at = {now} + :ttl "
                "WHERE job_id = :job_id AND owner = :owner"
            ),
            # Libération : supprimé si la fenêtre `min_hold` est passée…
            "release": (
                f"DELETE FROM {t} WHERE job_id = :job_id AND owner = :owner "
                f"AND acquired_at + :hold <= {now}"
            ),
            # …sinon raccourci à la fin de cette fenêtre (il expirera tout seul).
            "shorten": (
                f"UPDATE {t} SET expires_at = acquired_at + :hold "
                "WHERE job_id = :job_id AND owner = :owner"
            ),
            "owner": f"SELECT owner FROM {t} WHERE job_id = :job_id",
        }
        if self.dialect in _UPSERT:
            # Une seule instruction, atomique : insère, ou reprend si expiré, ou rien.
            sql["acquire"] = (
                f"INSERT INTO {t} (job_id, owner, acquired_at, expires_at) "
                f"VALUES (:job_id, :owner, {now}, {now} + :ttl) "
                "ON CONFLICT (job_id) DO UPDATE SET owner = excluded.owner, "
                "acquired_at = excluded.acquired_at, expires_at = excluded.expires_at "
                f"WHERE {t}.expires_at < {now}"
            )
        else:
            # MySQL/MariaDB : `steal` d'abord, puis une insertion qui ignore le doublon.
            # Les deux sont atomiques une à une, et un seul des concurrents peut
            # réussir l'une OU l'autre (clé primaire, condition d'expiration).
            sql["insert"] = (
                f"INSERT IGNORE INTO {t} (job_id, owner, acquired_at, expires_at) "
                f"VALUES (:job_id, :owner, {now}, {now} + :ttl)"
            )
        return sql

    async def _run(self, statement: str, params: dict | None = None) -> Any:
        """Exécute UNE instruction dans sa propre transaction et rend le résultat."""
        return await run_statement(self._engine, statement, params)

    # ── API ───────────────────────────────────────────────────

    async def setup(self) -> None:
        """Crée la table des baux si elle n'existe pas (idempotent, concurrent-sûr)."""
        try:
            await self._run(self._sql["create"])
        except Exception:
            # Deux processus qui démarrent ensemble peuvent tous deux passer le
            # IF NOT EXISTS : si la table est là, l'erreur de l'un est sans objet.
            await self._run(f"SELECT 1 FROM {self.table} WHERE 1 = 0")

    async def acquire(self, job_id: str, owner: str) -> bool:
        """Prend le bail s'il est libre ou expiré. `False` : un autre le tient."""
        params = {"job_id": job_id, "owner": owner, "ttl": self.ttl}
        if "acquire" in self._sql:
            return (await self._run(self._sql["acquire"], params)).rowcount == 1
        if (await self._run(self._sql["steal"], params)).rowcount == 1:
            return True
        return (await self._run(self._sql["insert"], params)).rowcount == 1

    async def renew(self, job_id: str, owner: str) -> bool:
        """Prolonge SON bail. `False` : il a été perdu (expiré puis repris)."""
        params = {"job_id": job_id, "owner": owner, "ttl": self.ttl}
        return (await self._run(self._sql["renew"], params)).rowcount == 1

    async def release(self, job_id: str, owner: str) -> None:
        """Libère SON bail — après `min_hold` ; avant, le raccourcit à cette échéance."""
        params = {"job_id": job_id, "owner": owner, "hold": self.min_hold}
        if (await self._run(self._sql["release"], params)).rowcount == 1:
            return
        await self._run(self._sql["shorten"], params)

    async def holder(self, job_id: str) -> str | None:
        """Propriétaire inscrit pour ce job, expiré ou non (diagnostic, tests)."""
        row = (await self._run(self._sql["owner"], {"job_id": job_id})).first()
        return None if row is None else row[0]
