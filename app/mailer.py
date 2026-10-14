"""Envio de e-mail (SMTP) para reset de senha, verificacao de e-mail e alertas.

- APP_ENV=test: nada sai; as mensagens ficam em ``outbox`` (os testes inspecionam).
- SMTP_HOST definido: envia por SMTP (STARTTLS por padrao).
- Sem SMTP_HOST: nao envia. Fora de producao o conteudo vai para o log (util p/ copiar o link em dev);
  em producao o conteudo NUNCA e logado, porque contem tokens.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Dict, List

from app.config import settings

logger = logging.getLogger("dashboard.mail")

outbox: List[Dict[str, str]] = []  # so e preenchida em APP_ENV=test


def send_email(to: str, subject: str, body: str) -> bool:
    """Retorna True se a mensagem foi entregue ao servidor SMTP (ou capturada no modo de teste)."""
    if settings.APP_ENV.lower() == "test":
        outbox.append({"to": to, "subject": subject, "body": body})
        return True

    if not settings.SMTP_HOST:
        if settings.is_production:
            logger.warning("SMTP_HOST nao configurado: e-mail para %s nao enviado (%s)", to, subject)
        else:
            logger.info("SMTP_HOST nao configurado. E-mail para %s | %s\n%s", to, subject, body)
        return False

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # e-mail nunca derruba a requisicao
        logger.error("falha ao enviar e-mail para %s: %s", to, exc)
        return False
