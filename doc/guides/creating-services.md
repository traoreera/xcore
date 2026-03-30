# Création de Services

XCore permet de créer des services réutilisables qui peuvent être partagés entre plugins via le conteneur de services.

## Vue d'ensemble

Un service dans XCore est un composant qui :
- Implémente un cycle de vie (`init()`, `shutdown()`, `health_check()`, `status()`)
- Peut être utilisé par plusieurs plugins
- Est géré par le `ServiceContainer`

Il existe deux types de services :
1. **Services intégrés** — Base de données, cache, scheduler
2. **Extensions** — Services personnalisés que vous créez

## BaseService

Tous les services doivent hériter de `BaseService` :

```python
from xcore.services.base import BaseService, ServiceStatus


class MyService(BaseService):
    """Service personnalisé."""

    name = "my_service"

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self._client = None

    async def init(self) -> None:
        """Initialiser le service."""
        self._status = ServiceStatus.INITIALIZING

        # Connexion, warmup, etc.
        self._client = await self._connect()

        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        """Arrêter proprement le service."""
        if self._client:
            await self._client.close()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        """Vérifier la santé du service."""
        try:
            await self._client.ping()
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        """État actuel du service."""
        return {
            "name": self.name,
            "status": self._status.value,
            "config": self.config,
        }
```

## Créer une Extension

Les extensions sont des services personnalisés enregistrés dans la configuration.

### 1. Créer le Service

```python
# myapp/services/email.py
from xcore.services.base import BaseService, ServiceStatus
import aiosmtplib
from email.message import EmailMessage


class EmailService(BaseService):
    """Service d'envoi d'emails."""

    name = "email"

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.smtp_host = config.get("smtp_host", "localhost")
        self.smtp_port = config.get("smtp_port", 587)
        self.username = config.get("username")
        self.password = config.get("password")
        self.use_tls = config.get("tls", True)
        self._client = None
        self._sent_count = 0

    async def init(self) -> None:
        """Initialiser la connexion SMTP."""
        self._status = ServiceStatus.INITIALIZING

        self._client = aiosmtplib.SMTP(
            hostname=self.smtp_host,
            port=self.smtp_port,
            use_tls=self.use_tls
        )

        await self._client.connect()

        if self.username and self.password:
            await self._client.login(self.username, self.password)

        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        """Fermer la connexion SMTP."""
        if self._client:
            await self._client.quit()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        """Vérifier la connexion SMTP."""
        try:
            await self._client.noop()
            return True, f"Connected to {self.smtp_host}:{self.smtp_port}"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        """État du service."""
        return {
            "name": self.name,
            "status": self._status.value,
            "smtp_host": self.smtp_host,
            "sent_count": self._sent_count,
        }

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None
    ) -> dict:
        """Envoyer un email."""
        message = EmailMessage()
        message["From"] = self.username
        message["To"] = to
        message["Subject"] = subject

        if html:
            message.add_alternative(html, subtype="html")
        else:
            message.set_content(body)

        await self._client.send_message(message)
        self._sent_count += 1

        return {"sent": True, "to": to}

    async def send_bulk(
        self,
        recipients: list[str],
        subject: str,
        body: str
    ) -> dict:
        """Envoyer en masse."""
        results = []
        for recipient in recipients:
            try:
                result = await self.send_email(recipient, subject, body)
                results.append({"to": recipient, "status": "sent"})
            except Exception as e:
                results.append({"to": recipient, "status": "error", "error": str(e)})

        return {"results": results}
```

### 2. Configurer l'Extension

```yaml
# xcore.yaml
services:
  extensions:
    email:
      module: myapp.services.email:EmailService
      config:
        smtp_host: "${SMTP_HOST}"
        smtp_port: "${SMTP_PORT}"
        username: "${SMTP_USER}"
        password: "${SMTP_PASSWORD}"
        tls: true
```

### 3. Utiliser dans un Plugin

```python
from xcore.sdk import TrustedBase, ok


class NotificationPlugin(TrustedBase):

    async def on_load(self) -> None:
        self.email = self.get_service("ext.email")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "send_welcome":
            user_email = payload["email"]
            username = payload["username"]

            await self.email.send_email(
                to=user_email,
                subject="Bienvenue !",
                body=f"Bonjour {username}, bienvenue sur notre plateforme !",
                html=f"<h1>Bonjour {username}</h1><p>Bienvenue !</p>"
            )

            return ok(message="Email sent")

        if action == "send_bulk":
            await self.email.send_bulk(
                recipients=payload["recipients"],
                subject=payload["subject"],
                body=payload["body"]
            )
            return ok(message="Bulk email sent")

        return ok()
```

## Exemples de Services

### Service de Stockage S3

```python
# myapp/services/storage.py
from xcore.services.base import BaseService, ServiceStatus
import aioboto3


class S3StorageService(BaseService):
    """Service de stockage S3."""

    name = "storage"

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.bucket = config["bucket"]
        self.region = config.get("region", "us-east-1")
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
        self.endpoint_url = config.get("endpoint_url")  # Pour MinIO
        self._session = None
        self._client = None

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING

        self._session = aioboto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

        self._client = self._session.client(
            "s3",
            endpoint_url=self.endpoint_url
        )

        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            async with self._client as client:
                await client.head_bucket(Bucket=self.bucket)
            return True, f"Bucket {self.bucket} accessible"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "bucket": self.bucket,
            "region": self.region,
        }

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Uploader un fichier."""
        async with self._client as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type
            )
        return f"s3://{self.bucket}/{key}"

    async def download(self, key: str) -> bytes:
        """Télécharger un fichier."""
        async with self._client as client:
            response = await client.get_object(Bucket=self.bucket, Key=key)
            return await response["Body"].read()

    async def delete(self, key: str) -> bool:
        """Supprimer un fichier."""
        async with self._client as client:
            await client.delete_object(Bucket=self.bucket, Key=key)
        return True

    async def list_objects(self, prefix: str = "") -> list[dict]:
        """Lister les objets."""
        async with self._client as client:
            response = await client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            return [
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "modified": obj["LastModified"].isoformat()
                }
                for obj in response.get("Contents", [])
            ]
```

Configuration :

```yaml
services:
  extensions:
    storage:
      module: myapp.services.storage:S3StorageService
      config:
        bucket: "${S3_BUCKET}"
        region: "${AWS_REGION}"
        access_key: "${AWS_ACCESS_KEY}"
        secret_key: "${AWS_SECRET_KEY}"
        # Pour MinIO
        # endpoint_url: "http://localhost:9000"
```

### Service de Paiement Stripe

```python
# myapp/services/payments.py
from xcore.services.base import BaseService, ServiceStatus
import stripe


class StripeService(BaseService):
    """Service de paiement Stripe."""

    name = "payments"

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.api_key = config["api_key"]
        self.webhook_secret = config.get("webhook_secret")
        stripe.api_key = self.api_key
        self._transactions = []

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING

        # Vérifier la clé API
        try:
            stripe.Account.retrieve()
        except stripe.error.AuthenticationError as e:
            raise ValueError(f"Invalid Stripe API key: {e}")

        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            stripe.Account.retrieve()
            return True, "Stripe API accessible"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "transactions_count": len(self._transactions),
        }

    async def create_payment_intent(
        self,
        amount: int,
        currency: str = "eur",
        metadata: dict | None = None
    ) -> dict:
        """Créer un payment intent."""
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata or {}
        )

        self._transactions.append({
            "id": intent.id,
            "amount": amount,
            "currency": currency,
            "status": intent.status
        })

        return {
            "client_secret": intent.client_secret,
            "id": intent.id,
            "status": intent.status
        }

    async def confirm_payment(self, payment_intent_id: str) -> dict:
        """Confirmer un paiement."""
        intent = stripe.PaymentIntent.confirm(payment_intent_id)
        return {
            "id": intent.id,
            "status": intent.status,
            "amount": intent.amount
        }

    async def create_customer(self, email: str, name: str | None = None) -> dict:
        """Créer un client."""
        customer = stripe.Customer.create(
            email=email,
            name=name
        )
        return {"id": customer.id, "email": customer.email}

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str
    ) -> dict:
        """Créer un abonnement."""
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}]
        )
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end
        }
```

### Service de Cache Distribué

```python
# myapp/services/distributed_cache.py
from xcore.services.base import BaseService, ServiceStatus
import redis.asyncio as redis
import json
import pickle


class DistributedCacheService(BaseService):
    """Service de cache distribué avec Redis."""

    name = "distributed_cache"

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.redis_url = config.get("url", "redis://localhost:6379")
        self.default_ttl = config.get("ttl", 3600)
        self._redis = None
        self._hits = 0
        self._misses = 0

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING

        self._redis = redis.from_url(self.redis_url, decode_responses=False)
        await self._redis.ping()

        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        if self._redis:
            await self._redis.close()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            await self._redis.ping()
            return True, "Redis connection OK"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "name": self.name,
            "status": self._status.value,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
        }

    async def get(self, key: str, default=None) -> any:
        """Récupérer une valeur."""
        value = await self._redis.get(key)

        if value is None:
            self._misses += 1
            return default

        self._hits += 1
        return pickle.loads(value)

    async def set(
        self,
        key: str,
        value: any,
        ttl: int | None = None
    ) -> bool:
        """Stocker une valeur."""
        serialized = pickle.dumps(value)
        await self._redis.set(
            key,
            serialized,
            ex=ttl or self.default_ttl
        )
        return True

    async def delete(self, key: str) -> bool:
        """Supprimer une clé."""
        await self._redis.delete(key)
        return True

    async def exists(self, key: str) -> bool:
        """Vérifier si une clé existe."""
        return await self._redis.exists(key) > 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Incrémenter un compteur."""
        return await self._redis.incrby(key, amount)

    async def expire(self, key: str, ttl: int) -> bool:
        """Définir l'expiration d'une clé."""
        return await self._redis.expire(key, ttl)

    async def clear_pattern(self, pattern: str) -> int:
        """Supprimer toutes les clés correspondant à un pattern."""
        keys = await self._redis.keys(pattern)
        if keys:
            await self._redis.delete(*keys)
        return len(keys)
```

## Intégration avec le Event Bus

Les services peuvent émettre des événements :

```python
from xcore.kernel.events.bus import EventBus


class EmailService(BaseService):

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self._event_bus = EventBus()

    async def send_email(self, to: str, subject: str, body: str) -> dict:
        # ... envoi de l'email ...

        # Émettre un événement
        await self._event_bus.emit("email.sent", {
            "to": to,
            "subject": subject,
            "timestamp": time.time()
        })

        return {"sent": True}
```

Dans le plugin :

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.email = self.get_service("ext.email")

        # S'abonner aux événements du service
        self.email._event_bus.on("email.sent", self._on_email_sent)

    async def _on_email_sent(self, event):
        print(f"Email sent to {event.data['to']}")
```

## Intégration avec les Hooks

Les services peuvent aussi utiliser le HookManager :

```python
from xcore.kernel.events.hooks import HookManager


class PaymentService(BaseService):

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        self._hooks = HookManager()

        # Enregistrer des hooks par défaut
        @self._hooks.on("payment.before_process", priority=100)
        async def validate_payment(event):
            if event.data["amount"] <= 0:
                event.cancel()

    async def process_payment(self, amount: int, currency: str) -> dict:
        # Exécuter les hooks pré-traitement
        await self._hooks.emit("payment.before_process", {
            "amount": amount,
            "currency": currency
        })

        # Traitement du paiement...

        # Exécuter les hooks post-traitement
        await self._hooks.emit("payment.after_process", {
            "amount": amount,
            "currency": currency,
            "status": "completed"
        })

        return {"status": "completed"}
```

## Bonnes Pratiques

1. **Gestion des erreurs** — Toujours gérer les erreurs dans `init()` et `health_check()`
2. **Timeouts** — Utiliser des timeouts dans les opérations réseau
3. **Reconnexion** — Implémenter la logique de reconnexion si nécessaire
4. **Métriques** — Exposer des métriques via `status()`
5. **Clean shutdown** — Toujours fermer les connexions dans `shutdown()`

```python
class RobustService(BaseService):
    """Exemple de service robuste."""

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING

        # Retry avec backoff
        for attempt in range(5):
            try:
                self._client = await self._connect(timeout=10)
                break
            except Exception as e:
                if attempt == 4:
                    self._status = ServiceStatus.FAILED
                    raise
                await asyncio.sleep(2 ** attempt)

        self._status = ServiceStatus.READY

    async def health_check(self) -> tuple[bool, str]:
        try:
            # Timeout court pour le health check
            await asyncio.wait_for(self._client.ping(), timeout=2.0)
            return True, "OK"
        except asyncio.TimeoutError:
            self._status = ServiceStatus.DEGRADED
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    async def shutdown(self) -> None:
        if self._client:
            try:
                await asyncio.wait_for(self._client.close(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force close
                self._client.force_close()
        self._status = ServiceStatus.STOPPED
```

## Next Steps

- [Services Guide](./services.md) — Utiliser les services dans les plugins
- [Events](./events.md) — Communication inter-plugins
- [Monitoring](./monitoring.md) — Observer les services
