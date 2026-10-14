"""Configuracao dos alertas de orcamento estourado (e-mail e/ou webhook)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import alerts, models, schemas
from app.auth import get_current_user, require_writer
from app.database import get_db

router = APIRouter(prefix="/alerts", tags=["Alertas"])


def _get(db: Session, owner_id: int):
    return db.query(models.AlertSettings).filter(models.AlertSettings.owner_id == owner_id).first()


@router.get("/settings", response_model=schemas.AlertSettingsOut)
def get_settings(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    cfg = _get(db, user.id)
    if cfg is None:
        return {"email_enabled": False, "webhook_url": None, "threshold_pct": 100}
    return cfg


@router.put("/settings", response_model=schemas.AlertSettingsOut)
def put_settings(
    payload: schemas.AlertSettingsIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """`threshold_pct`: avisa quando o gasto do mes chega a esse % do limite (100 = limite atingido)."""
    if payload.webhook_url:
        try:
            alerts.validate_webhook_url(payload.webhook_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    cfg = _get(db, user.id)
    if cfg is None:
        cfg = models.AlertSettings(owner_id=user.id)
        db.add(cfg)
    cfg.email_enabled = payload.email_enabled
    cfg.webhook_url = payload.webhook_url
    cfg.threshold_pct = payload.threshold_pct
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/check", response_model=schemas.AlertCheckResult)
def check_now(db: Session = Depends(get_db), user: models.User = Depends(require_writer)):
    """Avalia os orcamentos agora e envia o que ainda nao foi avisado neste mes."""
    return {"sent": alerts.check_budget_alerts(db, user)}
