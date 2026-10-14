"""Ponto de entrada da API FastAPI."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.gzip import GZipMiddleware

from app import __version__, models  # noqa: F401  (registra os modelos no metadata)
from app.config import settings
from app.database import Base, engine, get_db
from app.logging_config import setup_logging
from app.routers import (
    accounts,
    admin,
    alerts_router,
    analytics_router,
    auth_router,
    budgets,
    categories,
    goals,
    recurring_router,
    transactions,
)

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("dashboard.access")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.ADMIN_USERNAMES.strip():
        logging.getLogger("dashboard").warning(
            "ADMIN_USERNAMES foi descontinuada e e IGNORADA (cadastro publico nunca concede admin). "
            "Crie o admin com: python -m app.cli create-admin <usuario> <email>"
        )
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Dashboard Analytics API",
    description="API RESTful para analise de financas pessoais: transacoes, orcamentos, "
    "previsao, anomalias e insights.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Content-Disposition"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.1f}"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


app.include_router(auth_router.router)
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(categories.router)
app.include_router(accounts.router)
app.include_router(goals.router)
app.include_router(recurring_router.router)
app.include_router(alerts_router.router)
app.include_router(analytics_router.router)
app.include_router(admin.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Dashboard Analytics API", "docs": "/docs", "version": __version__}


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "down"})
    return {"status": "healthy", "database": "up", "version": __version__}
