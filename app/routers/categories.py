"""Gerenciamento de categorias: listar, renomear e mesclar.

Categoria e texto livre nas transacoes e o orcamento depende do nome exato. Renomear/mesclar
atualiza, de uma vez, transacoes, regras recorrentes e orcamentos do usuario.

Mesclagem de orcamentos: se o destino ja tem limite, ele prevalece e o da origem e descartado;
se nao tem, o limite da origem passa para o destino.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, require_writer
from app.cache import get_cache, user_ns
from app.database import get_db

router = APIRouter(prefix="/categories", tags=["Categorias"])


def _key(name: str) -> str:
    key = name.strip().lower()
    if not key or len(key) > 80:
        raise HTTPException(status_code=422, detail="Categoria invalida")
    return key


def _move(db: Session, owner_id: int, old: str, new: str) -> dict:
    """Move tudo de `old` para `new` (sem commit). Retorna {'transactions': n, 'merged': bool}."""
    T, B, R = models.Transaction, models.Budget, models.RecurringRule
    tx_count = db.query(func.count(T.id)).filter(T.owner_id == owner_id, T.category == old).scalar() or 0
    budget_old = db.query(B).filter(B.owner_id == owner_id, B.category == old).first()
    rules = db.query(func.count(R.id)).filter(R.owner_id == owner_id, R.category == old).scalar() or 0
    if not tx_count and not budget_old and not rules:
        raise HTTPException(status_code=404, detail=f"Categoria '{old}' nao encontrada")

    target_in_use = (
        db.query(T.id).filter(T.owner_id == owner_id, T.category == new).first() is not None
        or db.query(B.id).filter(B.owner_id == owner_id, B.category == new).first() is not None
    )

    db.query(T).filter(T.owner_id == owner_id, T.category == old).update(
        {"category": new}, synchronize_session=False
    )
    db.query(R).filter(R.owner_id == owner_id, R.category == old).update(
        {"category": new}, synchronize_session=False
    )
    if budget_old:
        budget_new = db.query(B).filter(B.owner_id == owner_id, B.category == new).first()
        if budget_new:
            db.delete(budget_old)  # o limite do destino prevalece
        else:
            budget_old.category = new
    db.flush()  # a sessao tem autoflush desligado: sem isto, a proxima origem nao enxerga o orcamento movido
    return {"transactions": int(tx_count), "merged": target_in_use}


@router.get("/", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    T, B = models.Transaction, models.Budget
    counts = dict(
        db.query(T.category, func.count(T.id)).filter(T.owner_id == user.id).group_by(T.category).all()
    )
    limits = {b.category: float(b.monthly_limit) for b in db.query(B).filter(B.owner_id == user.id).all()}
    names = sorted(set(counts) | set(limits))
    return [
        schemas.CategoryOut(category=n, transactions=int(counts.get(n, 0)), budget_limit=limits.get(n))
        for n in names
    ]


@router.put("/{name:path}", response_model=schemas.CategoryChangeResult)
def rename_category(
    name: str,
    payload: schemas.CategoryRename,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Renomeia. Se o novo nome ja existir, as duas categorias sao unidas."""
    old, new = _key(name), payload.new_name
    if old == new:
        raise HTTPException(status_code=400, detail="O novo nome e igual ao atual")
    result = _move(db, user.id, old, new)
    db.commit()
    get_cache().invalidate(user_ns(user.id))
    return {"target": new, "transactions_updated": result["transactions"], "merged": result["merged"]}


@router.post("/merge", response_model=schemas.CategoryChangeResult)
def merge_categories(
    payload: schemas.CategoryMerge,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_writer),
):
    """Une varias categorias de origem em uma de destino."""
    target = _key(payload.target)
    sources = [s for s in payload.sources if s != target]
    if not sources:
        raise HTTPException(status_code=400, detail="Informe ao menos uma origem diferente do destino")
    # valida tudo antes de mexer: ou move todas ou nenhuma (o commit e unico no final)
    total, merged = 0, False
    for src in sources:
        res = _move(db, user.id, src, target)
        total += res["transactions"]
        merged = merged or res["merged"]
    db.commit()
    get_cache().invalidate(user_ns(user.id))
    return {"target": target, "transactions_updated": total, "merged": True if len(sources) > 1 else merged}
