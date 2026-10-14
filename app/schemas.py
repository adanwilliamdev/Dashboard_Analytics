"""Schemas Pydantic (validacao de entrada/saida)."""
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.utils import to_local_naive

# bcrypt so considera os 72 primeiros BYTES da senha; acima disso o restante seria ignorado em silencio
BCRYPT_MAX_BYTES = 72

TxType = Literal["income", "expense"]


def _norm_category(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip().lower()
    return value or "geral"


def _check_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"senha excede {BCRYPT_MAX_BYTES} bytes (caracteres acentuados ocupam mais de 1 byte)"
        )
    return value


# ---------- Usuarios / Auth ----------
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    # a regra de caracteres vale so para novos cadastros (nao quebra usuarios antigos)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=BCRYPT_MAX_BYTES)

    @field_validator("username")
    @classmethod
    def _lowercase_username(cls, v: str) -> str:
        # login e unicidade ignoram maiusculas ("Admin" e "admin" sao a mesma conta)
        return v.lower()

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        return _check_password_bytes(v)


Role = Literal["user", "viewer", "admin"]


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: Role = "user"
    is_active: bool = True
    email_verified: bool = False
    created_at: datetime


class AdminUserOut(UserOut):
    transaction_count: int = 0


class RoleIn(BaseModel):
    role: Role


class ActiveIn(BaseModel):
    is_active: bool


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=BCRYPT_MAX_BYTES)

    @field_validator("new_password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        return _check_password_bytes(v)


class ForgotPassword(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str = Field(..., min_length=10, max_length=2000)
    new_password: str = Field(..., min_length=8, max_length=BCRYPT_MAX_BYTES)

    @field_validator("new_password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        return _check_password_bytes(v)


class TokenIn(BaseModel):
    token: str = Field(..., min_length=10, max_length=2000)


class AccountDelete(BaseModel):
    """Confirmacao da exclusao da propria conta (LGPD): exige a senha atual."""

    password: str = Field(..., min_length=1, max_length=100)


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
    account_id: Optional[int] = Field(None, ge=1)

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
        return to_local_naive(v)


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=200)
    amount: Optional[float] = Field(None, gt=0, lt=1e12)
    category: Optional[str] = Field(None, max_length=80)
    type: Optional[TxType] = None
    date: Optional[datetime] = None
    # explicito: `null` desvincula a conta (os demais campos ignoram null)
    account_id: Optional[int] = Field(None, ge=1)

    @field_validator("category")
    @classmethod
    def _category(cls, v: Optional[str]) -> Optional[str]:
        return _norm_category(v)

    @field_validator("date")
    @classmethod
    def _date(cls, v: Optional[datetime]) -> Optional[datetime]:
        return to_local_naive(v)


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
    skipped: int  # linhas com erro de validacao
    duplicates: int = 0  # linhas ignoradas por ja existirem (data + valor + descricao + tipo)
    errors: List[ImportRowError] = []


# ---------- Orcamentos ----------
class BudgetIn(BaseModel):
    monthly_limit: float = Field(..., gt=0, lt=1e12)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    monthly_limit: float


# ---------- Categorias ----------
class CategoryOut(BaseModel):
    category: str
    transactions: int
    budget_limit: Optional[float] = None


class CategoryRename(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=80)

    @field_validator("new_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("nome nao pode ser vazio")
        return v


class CategoryMerge(BaseModel):
    sources: List[str] = Field(..., min_length=1, max_length=50)
    target: str = Field(..., min_length=1, max_length=80)

    @field_validator("sources")
    @classmethod
    def _sources(cls, v: List[str]) -> List[str]:
        cleaned = [c.strip().lower() for c in v if c and c.strip()]
        if not cleaned:
            raise ValueError("informe ao menos uma categoria de origem")
        return list(dict.fromkeys(cleaned))  # sem repetidas, mantendo a ordem

    @field_validator("target")
    @classmethod
    def _target(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("categoria de destino vazia")
        return v


class CategoryChangeResult(BaseModel):
    target: str
    transactions_updated: int
    merged: bool  # true quando o destino ja existia (categorias unidas)


# ---------- Contas / carteiras ----------
AccountType = Literal["checking", "savings", "cash", "credit", "investment"]


class AccountIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    type: AccountType = "checking"
    initial_balance: float = Field(0, gt=-1e12, lt=1e12)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome nao pode ser vazio")
        return v


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    type: Optional[AccountType] = None
    initial_balance: Optional[float] = Field(None, gt=-1e12, lt=1e12)

    @field_validator("name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("nome nao pode ser vazio")
        return v


class AccountOut(BaseModel):
    id: int
    name: str
    type: str
    initial_balance: float
    income: float
    expense: float
    balance: float
    transaction_count: int


# ---------- Metas de poupanca ----------
class GoalIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    target_amount: float = Field(..., gt=0, lt=1e12)
    saved_amount: float = Field(0, ge=0, lt=1e12)
    deadline: Optional[date] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome nao pode ser vazio")
        return v


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_amount: Optional[float] = Field(None, gt=0, lt=1e12)
    saved_amount: Optional[float] = Field(None, ge=0, lt=1e12)
    deadline: Optional[date] = None  # `null` explicito remove o prazo

    @field_validator("name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("nome nao pode ser vazio")
        return v


class GoalContribution(BaseModel):
    amount: float = Field(..., gt=-1e12, lt=1e12)  # negativo = retirada

    @field_validator("amount")
    @classmethod
    def _nonzero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("o valor nao pode ser zero")
        return v


class GoalOut(BaseModel):
    id: int
    name: str
    target_amount: float
    saved_amount: float
    deadline: Optional[date] = None
    remaining: float
    pct: float
    status: Literal["active", "completed", "overdue"]
    days_left: Optional[int] = None
    required_monthly: Optional[float] = None  # quanto guardar por mes para chegar no prazo


# ---------- Transacoes recorrentes ----------
Frequency = Literal["weekly", "monthly", "yearly"]


class RecurringIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., gt=0, lt=1e12)
    category: str = Field(default="geral", max_length=80)
    type: TxType = "expense"
    frequency: Frequency = "monthly"
    start_date: Optional[date] = None  # primeira ocorrencia (padrao: hoje)
    end_date: Optional[date] = None
    account_id: Optional[int] = Field(None, ge=1)

    @field_validator("description")
    @classmethod
    def _desc(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("descricao nao pode ser vazia")
        return v

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        return _norm_category(v)


class RecurringUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=200)
    amount: Optional[float] = Field(None, gt=0, lt=1e12)
    category: Optional[str] = Field(None, max_length=80)
    type: Optional[TxType] = None
    frequency: Optional[Frequency] = None
    next_date: Optional[date] = None
    end_date: Optional[date] = None  # `null` explicito remove o fim
    active: Optional[bool] = None
    account_id: Optional[int] = Field(None, ge=1)  # `null` explicito desvincula

    @field_validator("category")
    @classmethod
    def _category(cls, v: Optional[str]) -> Optional[str]:
        return _norm_category(v)


class RecurringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    description: str
    amount: float
    category: str
    type: str
    frequency: str
    next_date: date
    end_date: Optional[date] = None
    active: bool
    account_id: Optional[int] = None


class RecurringRunResult(BaseModel):
    created: int


# ---------- Alertas de orcamento ----------
class AlertSettingsIn(BaseModel):
    email_enabled: bool = False
    webhook_url: Optional[str] = Field(None, max_length=500)
    threshold_pct: int = Field(100, ge=50, le=200)

    @field_validator("webhook_url")
    @classmethod
    def _url(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        return v or None


class AlertSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    email_enabled: bool
    webhook_url: Optional[str] = None
    threshold_pct: int


class AlertSent(BaseModel):
    category: str
    pct_used: float
    channels: List[str]


class AlertCheckResult(BaseModel):
    sent: List[AlertSent]
