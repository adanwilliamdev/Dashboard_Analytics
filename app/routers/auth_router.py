"""Rotas de autenticacao e cadastro."""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import mailer, models, schemas
from app.auth import (
    burn_password_check,
    create_access_token,
    create_reset_token,
    create_verify_token,
    decode_purpose_token,
    get_current_user,
    hash_password,
    reset_token_matches,
    verify_password,
)
from app.cache import get_cache, user_ns
from app.config import settings
from app.database import SessionLocal, get_db
from app.security import login_limiter
from app.utils import utcnow

router = APIRouter(prefix="/auth", tags=["Autenticacao"])
logger = logging.getLogger("dashboard.auth")


def _frontend_link(query: str, token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/?{query}={token}"


def _send_verification_email(user_id: int) -> None:
    """Roda em segundo plano, depois que a sessao da requisicao fechou: busca o usuario de novo."""
    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if user is None:
            return
        _deliver_verification(user)


def _deliver_verification(user: models.User) -> None:
    link = _frontend_link("verify_token", create_verify_token(user))
    mailer.send_email(
        user.email,
        "Confirme seu e-mail",
        f"Ola, {user.username}.\n\nConfirme seu e-mail para ativar todos os recursos da conta:\n{link}\n\n"
        f"O link vale por {settings.EMAIL_VERIFY_EXPIRE_HOURS} horas. Se voce nao criou esta conta, ignore esta mensagem.\n",
    )


def _send_reset_email(user_id: int) -> None:
    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if user is None or not user.is_active:
            return
        _deliver_reset(user)


def _deliver_reset(user: models.User) -> None:
    link = _frontend_link("reset_token", create_reset_token(user))
    mailer.send_email(
        user.email,
        "Redefinicao de senha",
        f"Ola, {user.username}.\n\nPara criar uma nova senha, acesse:\n{link}\n\n"
        f"O link vale por {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutos e so pode ser usado uma vez. "
        "Se voce nao pediu isso, ignore esta mensagem: sua senha continua a mesma.\n",
    )


def _throttle(request: Request, action: str) -> None:
    """Limita pedidos de e-mail (reset/verificacao) por IP, reaproveitando o limitador do login."""
    ip = request.client.host if request.client else "unknown"
    key = f"{action}|{ip}"
    login_limiter.check(key)
    login_limiter.record_failure(key)  # conta todo pedido, nao so falhas


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(user: schemas.UserCreate, background: BackgroundTasks, db: Session = Depends(get_db)):
    # user.username ja vem em minusculas (schema); compara sem diferenciar caixa p/ pegar contas antigas
    if db.query(models.User).filter(func.lower(models.User.username) == user.username).first():
        raise HTTPException(status_code=400, detail="Username ja cadastrado")
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="E-mail ja cadastrado")

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        role="user",  # nunca "admin" por cadastro publico: use `python -m app.cli create-admin`
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:  # corrida entre dois cadastros simultaneos
        db.rollback()
        raise HTTPException(status_code=400, detail="Username ou e-mail ja cadastrado")
    db.refresh(new_user)
    background.add_task(_send_verification_email, new_user.id)
    return new_user


@router.post("/login", response_model=schemas.Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    username = form_data.username.strip().lower()
    key = ip + "|" + username
    login_limiter.check(key)

    user = db.query(models.User).filter(func.lower(models.User.username) == username).first()
    if user is None:
        burn_password_check(form_data.password)
    if not user or not verify_password(form_data.password, user.hashed_password):
        login_limiter.record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha invalidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta desativada")
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-mail nao verificado. Use o link enviado ao seu e-mail.",
        )

    login_limiter.reset(key)
    token = create_access_token(data={"sub": user.username, "tv": user.token_version or 0})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=204)
def change_password(
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.token_version = (current_user.token_version or 0) + 1  # derruba tokens ja emitidos
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------- reset de senha / verificacao
@router.post("/forgot-password", status_code=202)
def forgot_password(
    payload: schemas.ForgotPassword,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Envia o link de redefinicao. A resposta e sempre a mesma (nao revela se o e-mail existe)."""
    _throttle(request, "forgot")
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.email.lower()).first()
    if user is not None and user.is_active:
        background.add_task(_send_reset_email, user.id)  # em segundo plano: o tempo de resposta tambem nao revela
    return {"detail": "Se o e-mail estiver cadastrado, enviaremos as instrucoes para redefinir a senha."}


@router.post("/reset-password", status_code=204)
def reset_password(payload: schemas.PasswordReset, db: Session = Depends(get_db)):
    """Define nova senha com o token do e-mail. Uso unico: trocar a senha invalida o link."""
    data = decode_purpose_token(payload.token, "reset")
    user = db.query(models.User).filter(models.User.username == data["sub"]).first()
    if user is None or not user.is_active or not reset_token_matches(user, data):
        raise HTTPException(status_code=400, detail="Link invalido ou expirado")
    user.hashed_password = hash_password(payload.new_password)
    user.token_version = (user.token_version or 0) + 1  # derruba sessoes abertas
    db.commit()
    return Response(status_code=204)


@router.post("/resend-verification", status_code=202)
def resend_verification(
    request: Request,
    background: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
):
    if current_user.email_verified:
        return {"detail": "E-mail ja verificado."}
    _throttle(request, "verify")
    background.add_task(_send_verification_email, current_user.id)
    return {"detail": "Enviamos um novo link de verificacao para o seu e-mail."}


@router.post("/verify-email")
def verify_email(payload: schemas.TokenIn, db: Session = Depends(get_db)):
    data = decode_purpose_token(payload.token, "verify")
    user = db.query(models.User).filter(models.User.username == data["sub"]).first()
    # o token carrega o e-mail: se o e-mail da conta mudou depois, o link deixa de valer
    if user is None or not user.is_active or user.email != data.get("email"):
        raise HTTPException(status_code=400, detail="Link invalido ou expirado")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
    return {"verified": True}


# ----------------------------------------------------------------- LGPD
def _rows(db: Session, model, owner_id: int, order_by) -> List[Dict[str, Any]]:
    items = db.query(model).filter(model.owner_id == owner_id).order_by(order_by).all()
    return [{c.name: getattr(i, c.name) for c in model.__table__.columns} for i in items]


@router.get("/me/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Portabilidade (LGPD art. 18): todos os dados do titular em JSON. Nao inclui o hash da senha."""
    uid = current_user.id
    M = models
    payload = {
        "exported_at": utcnow().isoformat() + "Z",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "email_verified": current_user.email_verified,
            "created_at": current_user.created_at,
        },
        "transactions": _rows(db, M.Transaction, uid, M.Transaction.id),
        "budgets": _rows(db, M.Budget, uid, M.Budget.id),
        "accounts": _rows(db, M.Account, uid, M.Account.id),
        "goals": _rows(db, M.Goal, uid, M.Goal.id),
        "recurring_rules": _rows(db, M.RecurringRule, uid, M.RecurringRule.id),
        "alert_settings": _rows(db, M.AlertSettings, uid, M.AlertSettings.id),
        "alert_log": _rows(db, M.AlertLog, uid, M.AlertLog.id),
    }
    return JSONResponse(
        content=jsonable_encoder(payload),
        headers={"Content-Disposition": 'attachment; filename="meus_dados.json"'},
    )


@router.delete("/me", status_code=204)
def delete_my_account(
    payload: schemas.AccountDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Exclusao da conta e de TODOS os dados (LGPD art. 18, VI). Irreversivel; exige a senha."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha incorreta")
    if current_user.role == "admin":
        other_admins = (
            db.query(models.User.id)
            .filter(models.User.role == "admin", models.User.is_active.is_(True), models.User.id != current_user.id)
            .first()
        )
        if other_admins is None:
            raise HTTPException(status_code=400, detail="Voce e o unico administrador: promova outro antes de excluir")

    uid = current_user.id
    M = models
    # ordem respeita as chaves estrangeiras: dependentes primeiro
    db.query(M.AlertLog).filter(M.AlertLog.owner_id == uid).delete(synchronize_session=False)
    db.query(M.AlertSettings).filter(M.AlertSettings.owner_id == uid).delete(synchronize_session=False)
    db.query(M.Transaction).filter(M.Transaction.owner_id == uid).delete(synchronize_session=False)
    db.query(M.RecurringRule).filter(M.RecurringRule.owner_id == uid).delete(synchronize_session=False)
    db.query(M.Goal).filter(M.Goal.owner_id == uid).delete(synchronize_session=False)
    db.query(M.Budget).filter(M.Budget.owner_id == uid).delete(synchronize_session=False)
    db.query(M.Account).filter(M.Account.owner_id == uid).delete(synchronize_session=False)
    db.query(M.User).filter(M.User.id == uid).delete(synchronize_session=False)
    db.commit()
    get_cache().invalidate(user_ns(uid))
    logger.info("conta excluida a pedido do titular (user_id=%s)", uid)
    return Response(status_code=204)
