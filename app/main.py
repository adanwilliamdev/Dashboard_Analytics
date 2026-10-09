"""Ponto de entrada da API FastAPI."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth_router, transactions, analytics_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Dashboard Analytics API",
    description="API RESTful para dashboard de analise de dados (financas pessoais / e-commerce).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(transactions.router)
app.include_router(analytics_router.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "Dashboard Analytics API",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
