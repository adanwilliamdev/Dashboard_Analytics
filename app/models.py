"""Modelos ORM (SQLAlchemy)."""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import local_now, utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user", server_default="user")  # user | viewer | admin
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    # incrementado ao trocar a senha: invalida todos os JWTs emitidos antes (claim "tv")
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    # true depois que o usuario clica no link enviado por e-mail (POST /auth/verify-email)
    email_verified = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, default=utcnow)

    transactions = relationship("Transaction", back_populates="owner", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="owner", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_owner_date", "owner_id", "date"),
        Index("ix_tx_owner_type_category", "owner_id", "type", "category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String(200), nullable=False)
    # Numeric(12,2) no banco (exato); asdecimal=False entrega float ao Python
    amount = Column(Numeric(12, 2, asdecimal=False), nullable=False)
    category = Column(String(80), nullable=False, default="geral")
    type = Column(String(20), nullable=False, default="expense")
    date = Column(DateTime, nullable=False, default=local_now)  # horario de parede em APP_TIMEZONE
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # conta/carteira (opcional) e regra recorrente que gerou a transacao (opcional)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    recurring_rule_id = Column(Integer, ForeignKey("recurring_rules.id", ondelete="SET NULL"), nullable=True)

    owner = relationship("User", back_populates="transactions")


class Budget(Base):
    """Limite mensal de gastos por categoria."""

    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("owner_id", "category", name="uq_budget_owner_category"),)

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(80), nullable=False)
    monthly_limit = Column(Numeric(12, 2, asdecimal=False), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    owner = relationship("User", back_populates="budgets")


class Account(Base):
    """Conta/carteira: o saldo e o saldo inicial + receitas - despesas das transacoes vinculadas."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_account_owner_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    type = Column(String(20), nullable=False, default="checking", server_default="checking")
    initial_balance = Column(Numeric(12, 2, asdecimal=False), nullable=False, default=0, server_default="0")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)


class Goal(Base):
    """Meta de poupanca: valor alvo, quanto ja foi guardado e prazo opcional."""

    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    target_amount = Column(Numeric(12, 2, asdecimal=False), nullable=False)
    saved_amount = Column(Numeric(12, 2, asdecimal=False), nullable=False, default=0, server_default="0")
    deadline = Column(Date, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)


class RecurringRule(Base):
    """Transacao recorrente: gera sozinha uma transacao a cada ocorrencia vencida (app/recurring.py)."""

    __tablename__ = "recurring_rules"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String(200), nullable=False)
    amount = Column(Numeric(12, 2, asdecimal=False), nullable=False)
    category = Column(String(80), nullable=False, default="geral")
    type = Column(String(20), nullable=False, default="expense")
    frequency = Column(String(10), nullable=False, default="monthly")  # weekly | monthly | yearly
    anchor_day = Column(Integer, nullable=False, default=1)  # dia do mes original (evita "derivar" em meses curtos)
    next_date = Column(DateTime, nullable=False, index=True)  # proxima ocorrencia (meia-noite, horario local)
    end_date = Column(DateTime, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default=true())
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)


class AlertSettings(Base):
    """Como avisar o usuario quando um orcamento atinge o percentual configurado (e-mail e/ou webhook)."""

    __tablename__ = "alert_settings"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    email_enabled = Column(Boolean, nullable=False, default=False, server_default=false())
    webhook_url = Column(String(500), nullable=True)
    threshold_pct = Column(Integer, nullable=False, default=100, server_default="100")


class AlertLog(Base):
    """Um alerta por (categoria, mes, limiar): a UNIQUE impede reenvio e serve de trava contra corrida."""

    __tablename__ = "alert_logs"
    __table_args__ = (
        UniqueConstraint("owner_id", "category", "month", "threshold_pct", name="uq_alert_once"),
    )

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(80), nullable=False)
    month = Column(String(7), nullable=False)  # YYYY-MM
    threshold_pct = Column(Integer, nullable=False)
    sent_at = Column(DateTime, default=utcnow)


# Unicidade do username ignorando maiusculas ("Admin" == "admin"). Indice funcional: SQLite e Postgres.
Index("uq_users_username_lower", func.lower(User.username), unique=True)
