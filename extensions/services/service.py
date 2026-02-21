"""
WebhookService — envoi de webhooks HTTP sortants avec retry et signature HMAC.
StorageService — stockage de fichiers (local ou S3).
HealthService  — monitoring de santé avec tâche de fond.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from xcore import BaseService

# ─────────────────────────────────────────────────────────────
# WEBHOOK SERVICE
# ─────────────────────────────────────────────────────────────


class WebhookService(BaseService):
    """
    Service d'envoi de webhooks HTTP sortants.

    Config YAML :
        extensions:
          webhook:
            service: "integrations.extensions.services:WebhookService"
            env:
              WEBHOOK_SECRET: "${WEBHOOK_SECRET}"
            config:
              timeout: 10
              retries: 3
              retry_delay: 2
              secret_header: "X-Webhook-Signature"

    Usage :
        webhook = integration.get("webhook")
        await webhook.send("https://api.example.com/hook", {"event": "user.created", "id": 42})
        await webhook.send(url, payload, headers={"X-Custom": "value"})
    """

    async def setup(self):
        self._timeout = int(self.config.get("timeout", 10))
        self._retries = int(self.config.get("retries", 3))
        self._retry_delay = int(self.config.get("retry_delay", 2))
        self._secret = self.env.get("WEBHOOK_SECRET", "")
        self._header = self.config.get("secret_header", "X-Webhook-Signature")
        self.logger.info("WebhookService prêt")

    async def send(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        sign: bool = True,
    ) -> bool:
        """
        Envoie un webhook avec retry automatique.
        Signe le payload avec HMAC-SHA256 si un secret est configuré.
        """
        self._assert_ready()

        try:
            import aiohttp
        except ImportError:
            raise ImportError("aiohttp non installé : pip install aiohttp")

        body = json.dumps(payload, ensure_ascii=False)
        hdrs = {"Content-Type": "application/json", **(headers or {})}

        if sign and self._secret:
            sig = hmac.new(
                self._secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            hdrs[self._header] = f"sha256={sig}"

        for attempt in range(1, self._retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        data=body,
                        headers=hdrs,
                        timeout=aiohttp.ClientTimeout(total=self._timeout),
                    ) as resp:
                        if resp.status < 400:
                            self.logger.info(f"Webhook envoyé → {url} [{resp.status}]")
                            return True
                        self.logger.warning(
                            f"Webhook {url} → {resp.status} (tentative {attempt})"
                        )
            except Exception as e:
                self.logger.warning(f"Erreur webhook {url}: {e} (tentative {attempt})")

            if attempt < self._retries:
                await asyncio.sleep(self._retry_delay * attempt)

        self.logger.error(f"Webhook échoué après {self._retries} tentatives : {url}")
        return False

    async def teardown(self):
        pass


# ─────────────────────────────────────────────────────────────
# STORAGE SERVICE
# ─────────────────────────────────────────────────────────────


class StorageService(BaseService):
    """
    Service de stockage de fichiers.

    Config YAML :
        extensions:
          storage:
            service: "integrations.extensions.services:StorageService"
            env:
              AWS_ACCESS_KEY: "${AWS_ACCESS_KEY}"
              AWS_SECRET_KEY: "${AWS_SECRET_KEY}"
            config:
              backend: "local"    # local | s3
              local:
                base_path: "./uploads"
              s3:
                bucket: "mon-bucket"
                region: "eu-west-1"

    Usage :
        storage = integration.get("storage")
        path = await storage.save("photo.jpg", file_bytes)
        data = await storage.read("photo.jpg")
        ok   = await storage.delete("photo.jpg")
        urls = await storage.list("uploads/")
    """

    async def setup(self):
        self._backend = self.config.get("backend", "local")

        if self._backend == "local":
            base = self.config.get("local", {}).get("base_path", "./uploads")
            self._base = Path(base)
            self._base.mkdir(parents=True, exist_ok=True)

        elif self._backend == "s3":
            try:
                import boto3
            except ImportError:
                raise ImportError("boto3 non installé : pip install boto3")

            s3_cfg = self.config.get("s3", {})
            self._s3 = boto3.client(
                "s3",
                region_name=s3_cfg.get("region", "us-east-1"),
                aws_access_key_id=self.env.get("AWS_ACCESS_KEY"),
                aws_secret_access_key=self.env.get("AWS_SECRET_KEY"),
            )
            self._bucket = s3_cfg.get("bucket", "")

        else:
            raise ValueError(f"StorageService backend inconnu : '{self._backend}'")

        self.logger.info(f"StorageService prêt [backend={self._backend}]")

    async def save(self, filename: str, data: bytes, folder: str = "") -> str:
        """Sauvegarde un fichier. Retourne le chemin ou l'URI S3."""
        self._assert_ready()
        key = f"{folder}/{filename}".lstrip("/") if folder else filename

        if self._backend == "local":
            path = self._base / key
            path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.get_event_loop().run_in_executor(None, path.write_bytes, data)
            return str(path)

        elif self._backend == "s3":
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.put_object(Bucket=self._bucket, Key=key, Body=data),
            )
            return f"s3://{self._bucket}/{key}"

        raise ValueError(f"Backend inconnu : {self._backend}")

    async def read(self, filename: str) -> bytes:
        """Lit un fichier et retourne son contenu en bytes."""
        self._assert_ready()

        if self._backend == "local":
            path = self._base / filename
            return await asyncio.get_event_loop().run_in_executor(None, path.read_bytes)

        elif self._backend == "s3":
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.get_object(Bucket=self._bucket, Key=filename),
            )
            return resp["Body"].read()

        raise ValueError(f"Backend inconnu : {self._backend}")

    async def delete(self, filename: str) -> bool:
        """Supprime un fichier. Retourne True si succès."""
        self._assert_ready()
        try:
            if self._backend == "local":
                (self._base / filename).unlink(missing_ok=True)
            elif self._backend == "s3":
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._s3.delete_object(Bucket=self._bucket, Key=filename),
                )
            return True
        except Exception as e:
            self.logger.error(f"Erreur suppression '{filename}' : {e}")
            return False

    async def list(self, prefix: str = "") -> List[str]:
        """Liste les fichiers dans un dossier/préfixe."""
        self._assert_ready()

        if self._backend == "local":
            base = self._base / prefix if prefix else self._base
            if not base.exists():
                return []
            return [
                str(p.relative_to(self._base)) for p in base.rglob("*") if p.is_file()
            ]

        elif self._backend == "s3":
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix),
            )
            return [obj["Key"] for obj in resp.get("Contents", [])]

        return []

    async def teardown(self):
        pass


# ─────────────────────────────────────────────────────────────
# HEALTH SERVICE
# ─────────────────────────────────────────────────────────────


class HealthService(BaseService):
    """
    Service de monitoring de santé avec tâche de fond.

    Config YAML :
        extensions:
          health:
            enabled: true
            service: "integrations.extensions.services:HealthService"
            background: true
            background_mode: "async"
            background_restart: true
            config:
              check_interval: 30
              alert_on_failure: true
              notify_service: "notify"
              checks:
                - name: "database"
                  type: "database"
                  target: "default"
                - name: "redis"
                  type: "redis"
                  url: "redis://localhost:6379"
                - name: "api_externe"
                  type: "http"
                  url: "https://api.example.com/ping"
                  expected_status: 200

    Usage :
        health = integration.get("health")
        report = await health.check_all()
        # {"database": {"status": "ok", "detail": "connexion OK"}, ...}
    """

    async def setup(self):
        self._interval = int(self.config.get("check_interval", 30))
        self._alert_enabled = self.config.get("alert_on_failure", True)
        self._notify_svc = self.config.get("notify_service", "notify")
        self._checks_cfg = self.config.get("checks", [])
        self._last_report: Dict[str, Any] = {}
        self._failed_before: set = set()
        self.logger.info(
            f"HealthService prêt — {len(self._checks_cfg)} check(s) "
            f"(intervalle: {self._interval}s)"
        )

    # ── Checks ────────────────────────────────────────────────

    async def check_all(self) -> Dict[str, Any]:
        """Exécute tous les checks et retourne le rapport complet."""
        results = {}
        for check in self._checks_cfg:
            name = check.get("name", "?")
            try:
                ok, detail = await self._run_check(check)
                results[name] = {"status": "ok" if ok else "fail", "detail": detail}
            except Exception as e:
                results[name] = {"status": "error", "detail": str(e)}

        self._last_report = results
        return results

    async def _run_check(self, check: dict) -> tuple[bool, str]:
        kind = check.get("type", "http")

        if kind == "http":
            return await self._check_http(check)
        if kind == "database":
            return await self._check_database(check)
        if kind == "redis":
            return await self._check_redis(check)

        return False, f"type de check inconnu : '{kind}'"

    async def _check_http(self, check: dict) -> tuple[bool, str]:
        try:
            import aiohttp
        except ImportError:
            raise ImportError("aiohttp non installé : pip install aiohttp")

        url = check.get("url", "")
        expected = int(check.get("expected_status", 200))
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    return r.status == expected, f"HTTP {r.status}"
        except Exception as e:
            return False, str(e)

    async def _check_database(self, check: dict) -> tuple[bool, str]:
        try:
            db_mgr = self.get_service("db")
            target = check.get("target", "default")
            adapter = db_mgr.get(target)
            with adapter.session() as db:
                db.execute("SELECT 1")
            return True, "connexion OK"
        except Exception as e:
            return False, str(e)

    async def _check_redis(self, check: dict) -> tuple[bool, str]:
        try:
            import redis
        except ImportError:
            raise ImportError("redis non installé : pip install redis")

        try:
            client = redis.from_url(
                check.get("url", "redis://localhost:6379"),
                socket_timeout=3,
            )
            client.ping()
            return True, "pong"
        except Exception as e:
            return False, str(e)

    # ── Alertes ───────────────────────────────────────────────

    async def _send_alert(self, name: str, detail: str) -> None:
        try:
            notify = self.get_service(self._notify_svc)
            await notify.all(f"🚨 Health check échoué : *{name}* — {detail}")
        except Exception as e:
            self.logger.error(f"Échec envoi alerte health : {e}")

    # ── Tâche de fond ─────────────────────────────────────────

    async def run_async(self):
        """Boucle de monitoring — tourne indéfiniment en tâche de fond."""
        self.logger.info(f"Monitoring démarré (intervalle : {self._interval}s)")
        while True:
            await asyncio.sleep(self._interval)
            report = await self.check_all()

            for name, result in report.items():
                if result["status"] != "ok":
                    if name not in self._failed_before:
                        self.logger.warning(f"Check '{name}' FAIL : {result['detail']}")
                        self._failed_before.add(name)
                        if self._alert_enabled:
                            await self._send_alert(name, result["detail"])
                else:
                    if name in self._failed_before:
                        self.logger.info(f"Check '{name}' revenu OK")
                        self._failed_before.discard(name)

    @property
    def last_report(self) -> Dict[str, Any]:
        """Retourne le dernier rapport sans relancer les checks."""
        return dict(self._last_report)

    async def teardown(self):
        self._last_report.clear()
        self._failed_before.clear()
