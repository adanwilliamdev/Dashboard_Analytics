"""Schemas Pydantic (validacao de entrada/saida)."""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TxType = Literal["income", "expense"]


def _norm_category(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip().lower()
    return value or "geral"


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Converte datetimes com fuso para UTC naive (como o banco armazena)."""
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# ---------- Usuarios / Auth ----------
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    # a regra de caracteres vale so para novos cadastros (nao quebra usuarios antigos)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=100)


Role = Literal["user", "viewer", "admin"]


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: Role = "user"
    is_active: bool = True
    created_at: datetime


class AdminUserOut(UserOut):
    transaction_count: int = 0


class RoleIn(BaseModel):
    role: Role


class ActiveIn(BaseModel):
    is_active: bool


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# ---------- Transacoes ----------
class TransactionBase(BaseModel):
    description: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., gt=0, lt=1e12)
    category: str = Field(default="geral", max_length=80)
    type: TxType = "expense"
    date: Optional[datetime] = None

    @field_validator("description")
    @classmethod
    def _strip_description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("descricao nao pode ser vazia")
        return v

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        return _norm_category(v)

    @field_validator("date")
    @classmethod
    def _date(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _naive_utc(v)


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=200)
    amount: Optional[float] = Field(None, gt=0, lt=1e12)
    category: Optional[str] = Field(None, max_length=80)
    type: Optional[TxType] = None
    date: Optional[datetime] = None

    @field_validator("category")
    @classmethod
    def _category(cls, v: Optional[str]) -> Optional[str]:
        return _norm_category(v)

    @field_validator("date")
    @classmethod
    def _date(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _naive_utc(v)


class TransactionOut(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    date: datetime


class ImportRowError(BaseModel):
    row: int
    error: str


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: List[ImportRowError] = []


# ---------- Orcamentos ----------
class BudgetIn(BaseModel):
    monthly_limit: float = Field(..., gt=0, lt=1e12)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    monthly_limit: float
