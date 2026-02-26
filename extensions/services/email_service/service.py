"""
examples/services/email_service/service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extension de service : EmailService (SMTP async via aiosmtplib).

Démontre :
  ┌─────────────────────────────────────────────────────┐
  │  1. Héritage BaseService (contrat xcore)            │
  │  2. Configuration via dict (injection depuis YAML)  │
  │  3. Connexion SMTP async avec pool de connexion     │
  │  4. Templates HTML/texte intégrés                   │
  │  5. File d'envoi avec retry                         │
  │  6. health_check() et status() complets             │
  │  7. Métriques internes (emails envoyés/échoués)     │
  └─────────────────────────────────────────────────────┘

Déclaration dans xcore.yaml :
    services:
      extensions:
        email:
          module: examples.services.email_service.service:EmailService
          config:
            smtp_host: smtp.gmail.com
            smtp_port: 587
            smtp_user: ${SMTP_USER}
            smtp_password: ${SMTP_PASSWORD}
            from_address: noreply@example.com
            from_name: "Mon Application"
            use_tls: true
            timeout: 10
            max_retries: 3
            queue_size: 100

Accès depuis un plugin :
    email = self.get_service("ext.email")
    await email.send(
        to="alice@example.com",
        subject="Bienvenue !",
        body="<h1>Bonjour Alice</h1>",
        is_html=True,
    )
    await email.send_template(
        to="bob@example.com",
        template="welcome",
        context={"username": "Bob", "app_name": "Mon App"},
    )
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from xcore.services.base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.email")


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

@dataclass
class EmailConfig:
    smtp_host:     str  = "localhost"
    smtp_port:     int  = 587
    smtp_user:     str  = ""
    smtp_password: str  = ""
    from_address:  str  = "noreply@example.com"
    from_name:     str  = "xcore App"
    use_tls:       bool = True
    timeout:       int  = 10
    max_retries:   int  = 3
    queue_size:    int  = 100

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EmailConfig":
        return cls(
            smtp_host=str(d.get("smtp_host", "localhost")),
            smtp_port=int(d.get("smtp_port", 587)),
            smtp_user=str(d.get("smtp_user", "")),
            smtp_password=str(d.get("smtp_password", "")),
            from_address=str(d.get("from_address", "noreply@example.com")),
            from_name=str(d.get("from_name", "xcore App")),
            use_tls=bool(d.get("use_tls", True)),
            timeout=int(d.get("timeout", 10)),
            max_retries=int(d.get("max_retries", 3)),
            queue_size=int(d.get("queue_size", 100)),
        )


# ─────────────────────────────────────────────────────────────
# Message
# ─────────────────────────────────────────────────────────────

@dataclass
class EmailMessage:
    to:          str | list[str]
    subject:     str
    body:        str
    is_html:     bool        = False
    cc:          list[str]   = field(default_factory=list)
    bcc:         list[str]   = field(default_factory=list)
    reply_to:    str | None  = None
    attachments: list[dict]  = field(default_factory=list)
    # Metadata interne
    id:          str         = field(default_factory=lambda: str(time.time_ns()))
    attempts:    int         = 0
    created_at:  float       = field(default_factory=time.time)

    @property
    def recipients(self) -> list[str]:
        to = [self.to] if isinstance(self.to, str) else self.to
        return list(set(to + self.cc + self.bcc))


# ─────────────────────────────────────────────────────────────
# Templates HTML intégrés
# ─────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, str] = {
    "welcome": """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bienvenue</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
  <h1 style="color: #2563eb;">Bienvenue, {username} ! 👋</h1>
  <p>Ton compte sur <strong>{app_name}</strong> a été créé avec succès.</p>
  <p>Tu peux dès maintenant te connecter et découvrir toutes les fonctionnalités.</p>
  <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
  <p style="color: #6b7280; font-size: 12px;">
    Cet email a été envoyé automatiquement, merci de ne pas y répondre.
  </p>
</body>
</html>
""",
    "password_reset": """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Réinitialisation mot de passe</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
  <h1 style="color: #dc2626;">Réinitialisation de mot de passe 🔑</h1>
  <p>Bonjour {username},</p>
  <p>Une demande de réinitialisation de mot de passe a été effectuée pour ton compte.</p>
  <p>
    <a href="{reset_url}"
       style="background: #2563eb; color: white; padding: 12px 24px;
              text-decoration: none; border-radius: 6px; display: inline-block;">
      Réinitialiser mon mot de passe
    </a>
  </p>
  <p style="color: #6b7280;">Ce lien expire dans {expires_in_minutes} minutes.</p>
  <p style="color: #6b7280;">Si tu n'es pas à l'origine de cette demande, ignore cet email.</p>
</body>
</html>
""",
    "notification": """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
  <h2 style="color: #1f2937;">{title}</h2>
  <p>{message}</p>
  {action_button}
  <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
  <p style="color: #6b7280; font-size: 12px;">{app_name}</p>
</body>
</html>
""",
}


def _render_template(name: str, context: dict[str, Any]) -> str:
    """Rendu minimal par substitution de {clé}."""
    tpl = _TEMPLATES.get(name)
    if not tpl:
        raise KeyError(f"Template email inconnu : '{name}'. Disponibles : {list(_TEMPLATES.keys())}")
    try:
        return tpl.format(**context)
    except KeyError as e:
        raise ValueError(f"Template '{name}' : variable manquante {e}") from e


# ─────────────────────────────────────────────────────────────
# Service principal
# ─────────────────────────────────────────────────────────────

class EmailService(BaseService):
    """
    Service d'envoi d'email SMTP asynchrone.

    Fonctionnalités :
      - send()           → envoi direct (avec retry)
      - send_template()  → envoi depuis un template HTML intégré
      - send_bulk()      → envoi en masse (parallèle, max_concurrent)
      - queue()          → file d'envoi (fire-and-forget)
      - Templates : welcome, password_reset, notification

    Usage dans un plugin :
        email = self.get_service("ext.email")

        # Simple
        await email.send(to="alice@ex.com", subject="Hello", body="Bonjour !")

        # Template
        await email.send_template(
            to="alice@ex.com",
            template="welcome",
            context={"username": "Alice", "app_name": "MonApp"},
        )

        # Fire-and-forget (non bloquant)
        email.queue(to="alice@ex.com", subject="Notif", body="...")
    """

    name = "email"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._cfg     = EmailConfig.from_dict(config)
        self._queue:  asyncio.Queue[EmailMessage] | None = None
        self._worker: asyncio.Task | None = None
        self._smtp_available = False

        # Métriques
        self._sent_count    = 0
        self._failed_count  = 0
        self._queued_count  = 0
        self._last_sent_at: float | None = None

    # ── Cycle de vie ──────────────────────────────────────────

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING

        # Vérification de la dépendance aiosmtplib
        try:
            import aiosmtplib  # noqa: F401
            self._smtp_available = True
        except ImportError:
            logger.warning(
                "aiosmtplib non installé — envoi SMTP désactivé. "
                "pip install aiosmtplib"
            )
            self._smtp_available = False

        # File d'envoi async
        self._queue = asyncio.Queue(maxsize=self._cfg.queue_size)
        self._worker = asyncio.create_task(
            self._queue_worker(),
            name="email_queue_worker",
        )

        # Test de connexion SMTP
        if self._smtp_available:
            try:
                await self._test_connection()
                logger.info(
                    f"EmailService prêt → {self._cfg.smtp_host}:{self._cfg.smtp_port} "
                    f"(from={self._cfg.from_address})"
                )
                self._status = ServiceStatus.READY
            except Exception as e:
                logger.warning(f"EmailService : connexion SMTP échouée ({e}) → mode dégradé")
                self._status = ServiceStatus.DEGRADED
        else:
            self._status = ServiceStatus.DEGRADED

    async def shutdown(self) -> None:
        if self._worker and not self._worker.done():
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        self._status = ServiceStatus.STOPPED
        logger.info(f"EmailService arrêté — {self._sent_count} email(s) envoyé(s)")

    async def health_check(self) -> tuple[bool, str]:
        if not self._smtp_available:
            return False, "aiosmtplib non installé"
        try:
            await self._test_connection()
            return True, f"SMTP {self._cfg.smtp_host}:{self._cfg.smtp_port} accessible"
        except Exception as e:
            return False, f"SMTP inaccessible : {e}"

    def status(self) -> dict[str, Any]:
        return {
            "name":         self.name,
            "status":       self._status.value,
            "smtp_host":    self._cfg.smtp_host,
            "smtp_port":    self._cfg.smtp_port,
            "from":         self._cfg.from_address,
            "smtp_available": self._smtp_available,
            "queue_size":   self._queue.qsize() if self._queue else 0,
            "sent":         self._sent_count,
            "failed":       self._failed_count,
            "queued":       self._queued_count,
            "last_sent_at": self._last_sent_at,
        }

    # ── API publique ──────────────────────────────────────────

    async def send(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        *,
        is_html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
    ) -> bool:
        """
        Envoie un email de manière synchrone (attend le résultat).

        Returns:
            True si envoyé, False si échec (après max_retries tentatives).
        """
        msg = EmailMessage(
            to=to, subject=subject, body=body,
            is_html=is_html,
            cc=cc or [], bcc=bcc or [],
            reply_to=reply_to,
        )
        return await self._send_with_retry(msg)

    async def send_template(
        self,
        to: str | list[str],
        template: str,
        context: dict[str, Any],
        *,
        subject: str | None = None,
        cc: list[str] | None = None,
    ) -> bool:
        """
        Envoie un email depuis un template HTML intégré.

        Templates disponibles : welcome, password_reset, notification

        Args:
            to:       destinataire(s)
            template: nom du template
            context:  variables de substitution
            subject:  sujet (utilise context['subject'] si absent)
        """
        html_body = _render_template(template, context)
        email_subject = subject or context.get("subject", f"[{self._cfg.from_name}] Notification")
        return await self.send(to=to, subject=email_subject, body=html_body, is_html=True, cc=cc)

    async def send_bulk(
        self,
        messages: list[dict[str, Any]],
        max_concurrent: int = 5,
    ) -> dict[str, Any]:
        """
        Envoie plusieurs emails en parallèle (avec limite de concurrence).

        Args:
            messages: liste de dicts avec les clés to, subject, body, ...
            max_concurrent: nombre max d'envois simultanés

        Returns:
            {"sent": int, "failed": int, "total": int}
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _send_one(msg_dict: dict) -> bool:
            async with semaphore:
                return await self.send(**msg_dict)

        results = await asyncio.gather(
            *[_send_one(m) for m in messages],
            return_exceptions=False,
        )
        sent   = sum(1 for r in results if r)
        failed = len(results) - sent
        return {"sent": sent, "failed": failed, "total": len(results)}

    def queue(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        *,
        is_html: bool = False,
    ) -> bool:
        """
        Ajoute un email dans la file d'envoi (fire-and-forget, non bloquant).

        Returns:
            True si ajouté à la file, False si la file est pleine.
        """
        msg = EmailMessage(to=to, subject=subject, body=body, is_html=is_html)
        try:
            self._queue.put_nowait(msg)
            self._queued_count += 1
            return True
        except asyncio.QueueFull:
            logger.warning(f"File email pleine ({self._cfg.queue_size} messages)")
            return False

    def add_template(self, name: str, html_content: str) -> None:
        """Ajoute ou remplace un template HTML custom."""
        _TEMPLATES[name] = html_content
        logger.info(f"EmailService : template '{name}' enregistré")

    # ── Internals ─────────────────────────────────────────────

    async def _test_connection(self) -> None:
        """Tente une connexion SMTP pour vérifier la disponibilité."""
        import aiosmtplib
        async with aiosmtplib.SMTP(
            hostname=self._cfg.smtp_host,
            port=self._cfg.smtp_port,
            timeout=self._cfg.timeout,
        ) as smtp:
            if self._cfg.use_tls:
                await smtp.starttls()
            if self._cfg.smtp_user:
                await smtp.login(self._cfg.smtp_user, self._cfg.smtp_password)

    async def _send_with_retry(self, msg: EmailMessage) -> bool:
        """Tente l'envoi avec backoff exponentiel."""
        for attempt in range(1, self._cfg.max_retries + 1):
            msg.attempts = attempt
            try:
                await self._do_send(msg)
                self._sent_count += 1
                self._last_sent_at = time.time()
                logger.info(
                    f"Email envoyé → {msg.to} | sujet: {msg.subject!r} "
                    f"(tentative {attempt}/{self._cfg.max_retries})"
                )
                return True
            except Exception as e:
                logger.warning(
                    f"Email échec (tentative {attempt}/{self._cfg.max_retries}) "
                    f"→ {msg.to} : {e}"
                )
                if attempt < self._cfg.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))

        self._failed_count += 1
        logger.error(f"Email définitivement échoué → {msg.to} | {msg.subject!r}")
        return False

    async def _do_send(self, msg: EmailMessage) -> None:
        """Construit et envoie le message MIME via SMTP."""
        if not self._smtp_available:
            # Mode dégradé : log uniquement (utile pour les tests)
            logger.info(
                f"[EMAIL SIMULÉ] To: {msg.to} | Subject: {msg.subject} | "
                f"Body: {msg.body[:80]}..."
            )
            return

        import aiosmtplib

        # Construire le MIME
        mime_msg = MIMEMultipart("alternative")
        mime_msg["From"]    = f"{self._cfg.from_name} <{self._cfg.from_address}>"
        mime_msg["To"]      = ", ".join([msg.to] if isinstance(msg.to, str) else msg.to)
        mime_msg["Subject"] = msg.subject
        if msg.cc:
            mime_msg["Cc"] = ", ".join(msg.cc)
        if msg.reply_to:
            mime_msg["Reply-To"] = msg.reply_to

        # Partie texte
        text_body = _html_to_text(msg.body) if msg.is_html else msg.body
        mime_msg.attach(MIMEText(text_body, "plain", "utf-8"))

        # Partie HTML si applicable
        if msg.is_html:
            mime_msg.attach(MIMEText(msg.body, "html", "utf-8"))

        async with aiosmtplib.SMTP(
            hostname=self._cfg.smtp_host,
            port=self._cfg.smtp_port,
            timeout=self._cfg.timeout,
        ) as smtp:
            if self._cfg.use_tls:
                await smtp.starttls()
            if self._cfg.smtp_user:
                await smtp.login(self._cfg.smtp_user, self._cfg.smtp_password)
            await smtp.send_message(mime_msg, recipients=msg.recipients)

    async def _queue_worker(self) -> None:
        """Traitement continu de la file d'envoi."""
        logger.debug("Email queue worker démarré")
        while True:
            try:
                msg = await self._queue.get()
                await self._send_with_retry(msg)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue worker erreur inattendue : {e}")


def _html_to_text(html: str) -> str:
    """Conversion HTML → texte très simplifiée (sans dépendance)."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
