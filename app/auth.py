"""Autenticacao: hash de senhas (bcrypt direto) + JWT (PyJWT)."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

BCRYPT_MAX_BYTES = 72
_dummy_hash: Optional[str] = None


def hash_password(password: str) -> str:
    """Gera o hash bcrypt. Recusa senhas > 72 bytes em vez de trunca-las em silencio."""
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError(f"senha excede {BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    # Trunca em 72 bytes so na VERIFICACAO: contas antigas (criadas quando o limite era 100
    # caracteres) tem hash dos primeiros 72 bytes e precisam continuar entrando.
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:BCRYPT_MAX_BYTES], hashed.encode("ascii"))
    except ValueError:  # hash malformado
        return False


def burn_password_check(plain: str) -> None:
    """Gasta o mesmo tempo de um bcrypt quando o usuario nao existe (evita enumeracao)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password")
    verify_password(plain, _dummy_hash)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = data.copy()
    payload.update(
        {
            "iat": now,
            "exp": now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)),
        }
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        raise credentials_exception

    username = payload.get("sub")
    if not username:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    # tokens emitidos antes de uma troca de senha deixam de valer (tokens antigos sem "tv" = versao 0)
    if int(payload.get("tv", 0)) != int(user.token_version or 0):
        raise credentials_exception
    return user


def require_writer(user: models.User = Depends(get_current_user)) -> models.User:
    """Bloqueia o perfil somente-leitura (viewer) em rotas que gravam dados."""
    if user.role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil somente leitura")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return user
