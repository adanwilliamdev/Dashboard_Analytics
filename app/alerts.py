"""Alertas de orcamento por e-mail e/ou webhook.

Disparados em segundo plano depois de gravar despesas (criar/editar/importar/recorrentes). Cada
(categoria, mes, limiar) avisa uma unica vez: o registro em ``alert_logs`` e feito ANTES do envio,
e a UNIQUE do banco impede duplicidade mesmo com requisicoes simultaneas.

Webhook: so http(s) e, por padrao, so destinos publicos (anti-SSRF; ver ALERT_WEBHOOK_ALLOW_PRIVATE).
Redirecionamentos nao sao seguidos. Observacao: a checagem de IP e feita no cadastro e antes de cada
envio, mas nao elimina por completo o risco de DNS rebinding; em ambientes sensiveis, restrinja a
saida de rede do servidor.
"""
import ipaddress
import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import analytics, mailer, models
from app.config import settings
from app.database import SessionLocal
from app.utils import local_now

logger = logging.getLogger("dashboard.alerts")
WEBHOOK_TIMEOUT = 5


# ------------------------------------------------------------------ webhook
def validate_webhook_url(url: str) -> str:
    """Valida o destino. Levanta ValueError com mensagem amigavel se nao for aceitavel."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL do webhook deve comecar com http:// ou https://")
    if settings.is_production and parsed.scheme != "https":
        raise ValueError("Em producao o webhook deve usar https://")
    if parsed.username or parsed.password:
        raise ValueError("URL do webhook nao pode conter usuario/senha")
    if settings.ALERT_WEBHOOK_ALLOW_PRIVATE:
        return url
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise ValueError("Nao foi possivel resolver o endereco do webhook")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("O webhook deve apontar para um endereco publico (rede interna nao permitida)")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - recusa qualquer redirecionamento
        return None


def _post_webhook(url: str, payload: Dict[str, Any]) -> bool:
    try:
        validate_webhook_url(url)
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "dashboard-analytics/alerts"},
            method="POST",
        )
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(req, timeout=WEBHOOK_TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except (ValueError, urllib.error.URLError, OSError) as exc:
        logger.warning("webhook de alerta falhou (%s): %s", urlparse(url).hostname, exc)
        return False


# ----------------------------------------------------------------- avaliacao
def check_budget_alerts(db: Session, user: models.User) -> List[Dict[str, Any]]:
    """Avalia os orcamentos do mes e envia o que ainda nao foi avisado. Retorna o que foi enviado."""
    cfg: Optional[models.AlertSettings] = (
        db.query(models.AlertSettings).filter(models.AlertSettings.owner_id == user.id).first()
    )
    if cfg is None or not (cfg.email_enabled or cfg.webhook_url):
        return []

    month = local_now().strftime("%Y-%m")
    sent: List[Dict[str, Any]] = []
    for b in analytics.get_budget_status(db, user.id):
        if b["pct_used"] < cfg.threshold_pct:
            continue
        db.add(
            models.AlertLog(owner_id=user.id, category=b["category"], month=month, threshold_pct=cfg.threshold_pct)
        )
        try:
            db.commit()  # "reserva" o alerta: quem perder a corrida cai no IntegrityError
        except IntegrityError:
            db.rollback()
            continue

        channels: List[str] = []
        if cfg.email_enabled and mailer.send_email(
            user.email,
            f"Orcamento de {b['category']} em {b['pct_used']:.0f}% do limite",
            (
                f"Ola, {user.username}.\n\n"
                f"Em {month}, voce ja gastou R$ {b['spent']:.2f} de R$ {b['monthly_limit']:.2f} "
                f"({b['pct_used']:.0f}%) na categoria '{b['category']}'.\n"
                f"Restante: R$ {b['remaining']:.2f}.\n"
            ),
        ):
            channels.append("email")
        if cfg.webhook_url and _post_webhook(
            cfg.webhook_url,
            {
                "event": "budget_alert",
                "month": month,
                "category": b["category"],
                "spent": b["spent"],
                "monthly_limit": b["monthly_limit"],
                "pct_used": b["pct_used"],
                "threshold_pct": cfg.threshold_pct,
                "status": b["status"],
            },
        ):
            channels.append("webhook")
        if not channels:
            # nenhum canal entregou: libera a reserva para uma nova tentativa na proxima gravacao
            db.query(models.AlertLog).filter(
                models.AlertLog.owner_id == user.id,
                models.AlertLog.category == b["category"],
                models.AlertLog.month == month,
                models.AlertLog.threshold_pct == cfg.threshold_pct,
            ).delete(synchronize_session=False)
            db.commit()
            continue
        sent.append({"category": b["category"], "pct_used": b["pct_used"], "channels": channels})
    return sent


def run_budget_alerts(user_id: int) -> None:
    """Ponto de entrada das tarefas em segundo plano (abre a propria sessao; nunca levanta)."""
    try:
        with SessionLocal() as db:
            user = db.get(models.User, user_id)
            if user is not None and user.is_active:
                check_budget_alerts(db, user)
    except Exception:
        logger.exception("falha ao avaliar alertas de orcamento (user_id=%s)", user_id)


def schedule(background: BackgroundTasks, user_id: int) -> None:
    background.add_task(run_budget_alerts, user_id)
