# Dashboard Analytics

Projeto completo de portfolio: **API RESTful (FastAPI) + Dashboard interativo (Streamlit)** para analise de financas pessoais ou metricas de e-commerce.

## Funcionalidades

- Autenticacao JWT com hash bcrypt
- CRUD completo de transacoes
- Analytics com Pandas: resumo, categorias, series temporais, top despesas
- Dashboard Streamlit interativo com Plotly
- Docker & Docker Compose
- Testes automatizados com pytest
- Documentacao automatica (Swagger/ReDoc)

## Stack

| Camada   | Tecnologia                          |
|----------|-------------------------------------|
| Backend  | FastAPI + SQLAlchemy + Pydantic     |
| Banco    | SQLite (dev) / PostgreSQL (prod)    |
| Dados    | Pandas + NumPy                      |
| Frontend | Streamlit + Plotly                  |
| Auth     | JWT (python-jose) + passlib[bcrypt] |
| DevOps   | Docker + Docker Compose             |

## Quickstart (local)

### 1. Ambiente virtual

    python -m venv .venv
    source .venv/bin/activate       # Linux/macOS
    .venv\Scripts\activate          # Windows
    pip install -r requirements.txt

### 2. Configuracao

    cp .env.example .env

### 3. Popular dados de exemplo (opcional)

    python seed_data.py

Cria usuario: demo / demo123

### 4. Subir a API

    uvicorn app.main:app --reload --port 8000

Acesse: http://localhost:8000/docs

### 5. Subir o Dashboard (outro terminal)

    streamlit run dashboard/app.py

Acesse: http://localhost:8501

## Docker

    docker compose up --build

- API: http://localhost:8000/docs
- Dashboard: http://localhost:8501

## Testes

    pytest -v

## Endpoints principais

### Auth

| Metodo | Rota           | Descricao            |
|--------|----------------|----------------------|
| POST   | /auth/register | Cadastro de usuario  |
| POST   | /auth/login    | Login (retorna JWT)  |
| GET    | /auth/me       | Dados do usuario     |

### Transacoes

| Metodo | Rota               | Descricao            |
|--------|--------------------|----------------------|
| POST   | /transactions/     | Criar transacao      |
| GET    | /transactions/     | Listar transacoes    |
| GET    | /transactions/{id} | Buscar transacao     |
| PUT    | /transactions/{id} | Atualizar transacao  |
| DELETE | /transactions/{id} | Excluir transacao    |

### Analytics

| Metodo | Rota                     | Descricao                       |
|--------|--------------------------|---------------------------------|
| GET    | /analytics/summary       | Receitas, despesas e saldo      |
| GET    | /analytics/by-category   | Totais agrupados por categoria  |
| GET    | /analytics/timeseries    | Serie diaria (income/expense)   |
| GET    | /analytics/top-expenses  | Maiores despesas                |

## Estrutura

    dashboard-analytics/
    |-- app/                 # Backend FastAPI
    |   |-- main.py
    |   |-- config.py
    |   |-- database.py
    |   |-- models.py
    |   |-- schemas.py
    |   |-- auth.py
    |   |-- analytics.py
    |   `-- routers/
    |-- dashboard/           # Frontend Streamlit
    |   `-- app.py
    |-- tests/               # Testes pytest
    |-- seed_data.py         # Dados de exemplo
    |-- Dockerfile
    |-- docker-compose.yml
    `-- requirements.txt

## Migrando para PostgreSQL

No .env:

    DATABASE_URL=postgresql://user:password@localhost:5432/dashboard

O driver psycopg2-binary ja esta no requirements.txt.

## Licenca

MIT
