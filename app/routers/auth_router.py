"""Rotas de autenticacao e cadastro."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import (
    burn_password_check,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.security import login_limiter

router = APIRouter(prefix="/auth", tags=["Autenticacao"])


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
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
