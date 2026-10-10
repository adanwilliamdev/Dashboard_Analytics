"""CRUD de transacoes + filtros, busca, exportacao e importacao CSV."""
import csv
import io
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import csv_io, models, reports, schemas
from app.auth import get_current_user, require_writer
from app.cache import get_cache, user_ns
from app.database import get_db
from app.utils import utcnow

router = APIRouter(prefix="/transactions", tags=["Transacoes"])

_SORTABLE = {
    "date": models.Transaction.date,
    "amount": models.Transaction.amount,
    "category": models.Transaction.category,
    "description": models.Transaction.description,
}


class TransactionFilters:
    """Filtros compartilhados por listagem e exportacao."""

    def __init__(
        self,
        category: Optional[str] = Query(None, description="Categoria exata"),
        type: Optional[Literal["income", "expense"]] = Query(None),
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        q: Optional[str] = Query(None, max_length=100, description="Busca na descricao"),
        min_amount: Optional[float] = Query(None, ge=0),
        max_amount: Optional[float] = Query(None, ge=0),
    ):
        self.category = category.strip().lower() if category else None
        self.type = type
        self.start_date = start_date
        self.end_date = end_date
        self.q = q.strip().lower() if q else None
        self.min_amount = min_amount
        self.max_amount = max_amount

    def apply(self, query, owner_id: int):
        T = models.Transaction
        query = query.filter(T.owner_id == owner_id)
        if self.category:
            query = query.filter(T.category == self.category)
        if self.type:
            query = query.filter(T.type == self.type)
        if self.start_date:
            query = query.filter(T.date >= self.start_date)
        if self.end_date:
            query = query.filter(T.date <= self.end_date)
        if self.q:
            query = query.filter(func.lower(T.description).contains(self.q, autoescape=True))
        if self.min_amount is not None:
            query = query.filter(T.amount >= self.min_amount)
        if self.max_amount is not None:
            query = query.filter(T.amount <= self.max_amount)
        return query


def _get_owned(db: Session, tx_id: int, owner_id: int) -> models.Transaction:
    tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == tx_id, models.Transaction.owner_id == owner_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")
    return tx


def _csv_safe(value: str) -> str:
    """Evita 'CSV injection' (formulas) ao abrir no Excel/Sheets."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@router.post("/", response_model=schemas.TransactionOut, status_code=201)
def create_transaction(
    payload: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_writer),
):
    tx = models.Transaction(
        description=payload.description,
        amount=payload.amount,
        category=payload.category,
        type=payload.type,
        date=payload.date or utcnow(),
        owner_id=current_user.id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    get_cache().invalidate(user_ns(current_user.id))
    return tx


@router.get("/", response_model=List[schemas.TransactionOut])
def list_transactions(
    response: Response,
    filters: TransactionFilters = Depends(),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: Literal["date", "amount", "category", "description"] = "date",
    order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Lista com filtros/ordenacao. O total filtrado vai no header `X-Total-Count`."""
    base = filters.apply(db.query(models.Transaction), current_user.id)
    response.headers["X-Total-Count"] = str(base.order_by(None).count())

    col = _SORTABLE[sort_by]
    ordering = col.asc() if order == "asc" else col.desc()
    return (
        base.order_by(ordering, models.Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/categories", response_model=List[str])
def list_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.Transaction.category)
        .filter(models.Transaction.owner_id == current_user.id)
        .distinct()
        .order_by(models.Transaction.category)
        .all()
    )
    return [r[0] for r in rows]


@router.get("/export")
def export_csv(
    filters: TransactionFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Exporta as transacoes (com os mesmos filtros da listagem) em CSV."""
    rows = (
        filters.apply(db.query(models.Transaction), current_user.id)
        .order_by(models.Transaction.date.desc(), models.Transaction.id.desc())
        .limit(100_000)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "date", "description", "category", "type", "amount"])
    for t in rows:
        writer.writerow(
            [t.id, t.date.strftime("%Y-%m-%d %H:%M:%S"), _csv_safe(t.description),
             _csv_safe(t.category), t.type, f"{t.amount:.2f}"]
        )
    filename = "transacoes_" + utcnow().strftime("%Y%m%d") + ".csv"
    return StreamingResponse(
        iter(["\ufeff" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
    )


@router.get("/export.xlsx")
def export_xlsx(
    filters: TransactionFilters = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Planilha Excel (Resumo, Transacoes, Categorias e Mensal) com os mesmos filtros."""
    items = (
        filters.apply(db.query(models.Transaction), current_user.id)
        .order_by(models.Transaction.date.desc(), models.Transaction.id.desc())
        .limit(100_000)
        .all()
    )
    data = reports.build_transactions_xlsx(
        [
            {"id": t.id, "date": t.date, "description": t.description, "category": t.category,
             "type": t.type, "amount": float(t.amount)}
            for t in items
        ]
    )
    filename = "transacoes_" + utcnow().strftime("%Y%m%d") + ".xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
    )


@router.post("/import", response_model=schemas.ImportResult)
def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_writer),
):
    """Importa CSV (colunas: description/descricao, amount/valor, category, type, date)."""
    raw = file.file.read(csv_io.MAX_BYTES + 1)
    if len(raw) > csv_io.MAX_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo maior que 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    parsed, errors = csv_io.parse_transactions_csv(text)
    valid = []
    for i, row in enumerate(parsed):
        try:
            item = schemas.TransactionCreate(**row)
        except ValidationError as exc:
            errors.append({"row": i + 2, "error": "; ".join(e["msg"] for e in exc.errors())})
            continue
        valid.append(
            models.Transaction(
                description=item.description,
                amount=item.amount,
                category=item.category,
                type=item.type,
                date=item.date or utcnow(),
                owner_id=current_user.id,
            )
        )
    if valid:
        db.add_all(valid)
        db.commit()
        get_cache().invalidate(user_ns(current_user.id))
    return {"imported": len(valid), "skipped": len(errors), "errors": errors[:20]}


@router.get("/{tx_id}", response_model=schemas.TransactionOut)
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned(db, tx_id, current_user.id)


@router.put("/{tx_id}", response_model=schemas.TransactionOut)
def update_transaction(
    tx_id: int,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_writer),
):
    tx = _get_owned(db, tx_id, current_user.id)
    # campos nao-anulaveis: ignora null explicito
    data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for key, value in data.items():
        setattr(tx, key, value)
    db.commit()
    db.refresh(tx)
    get_cache().invalidate(user_ns(current_user.id))
    return tx


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_writer),
):
    tx = _get_owned(db, tx_id, current_user.id)
    db.delete(tx)
    db.commit()
    get_cache().invalidate(user_ns(current_user.id))
    return Response(status_code=204)
