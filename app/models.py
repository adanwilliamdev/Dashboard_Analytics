"""Modelos ORM (SQLAlchemy)."""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils import utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user", server_default="user")  # user | viewer | admin
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
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
    date = Column(DateTime, nullable=False, default=utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

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
