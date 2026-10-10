# 📊 Dashboard Analytics

**API FastAPI + dashboard Streamlit para análise de finanças pessoais**: transações, orçamentos, comparativos, previsão de gastos, detecção de anomalias e insights automáticos.

> Projeto de portfólio que combina backend, engenharia de dados e visualização.

## ✨ Funcionalidades

| Área | O que tem |
|---|---|
| 🔐 Autenticação | JWT (PyJWT), bcrypt, bloqueio de força bruta no login (429), troca de senha, política de senha (mín. 8) |
| 💳 Transações | CRUD, filtros (texto, tipo, categoria, período, faixa de valor), ordenação, paginação (`X-Total-Count`), **importação e exportação CSV** (aceita formato pt-BR) |
| 🎯 Orçamentos | Limite mensal por categoria, consumo em tempo real, projeção de estouro até o fim do mês |
| 📈 Análises | Resumo com **comparação com o período anterior**, taxa de poupança, série diária sem buracos + saldo acumulado + média móvel, comparativo mensal, perfil por dia da semana |
| 🔮 Previsão | Projeção de despesas e saldo para 30 dias (nível + tendência amortecida + sazonalidade semanal) com faixa de ~80% |
| ⚠️ Anomalias | Gastos fora do padrão (z-score modificado, comparando cada item com o próprio histórico) |
| 🔁 Recorrentes | Detecta assinaturas e contas mensais e prevê a próxima data |
| 💡 Insights | Frases prontas em português geradas a partir dos dados |
| 📊 Dashboard | 5 abas (visão geral, análises, orçamentos, transações, insights), uma única chamada à API (`/analytics/overview`) |
| 📤 Relatórios | Excel (Resumo, Transações, Categorias, Mensal) e **PDF executivo** do período |
| ⚡ Cache | Visão geral em cache por usuário (30 s), invalidado a cada escrita; memória ou **Redis** (`REDIS_URL`) |
| 👥 Perfis | `user`, `viewer` (somente leitura) e `admin` (gerencia perfis e desativa contas em `/admin/users`) |
| 🗄️ Migrações | **Alembic** (`alembic upgrade head`), valores monetários em `NUMERIC(12,2)` |
| 🧪 Qualidade | Testes de unidade (núcleo analítico/CSV) e de API, CI no GitHub Actions, ruff |
| 🐳 Deploy | Docker não-root com healthchecks, Postgres no compose, override de desenvolvimento |

## 🏗️ Arquitetura

```text
app/
├── main.py              # FastAPI, middlewares (CORS, gzip, tempo de resposta), /health com ping no banco
├── config.py            # Settings (.env) + validação de SECRET_KEY em produção
├── database.py / models.py / schemas.py
├── auth.py / security.py
├── analytics_core.py    # análise PURA (pandas/numpy): sem banco, 100% testável
├── analytics.py         # carrega do banco e delega ao núcleo
├── csv_io.py            # parser tolerante de CSV
├── reports.py           # Excel e PDF (funções puras)
├── cache.py             # cache por usuário (memória/Redis)
└── routers/             # auth, transactions, budgets, analytics, admin
migrations/              # Alembic (0001 baseline, 0002 orçamentos/perfis/NUMERIC)
dashboard/app.py         # Streamlit
tests/                   # pytest
```

## 🚀 Executando localmente

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
python seed_data.py             # usuário demo: demo / demo1234  (6 meses de dados)
uvicorn app.main:app --reload   # API em http://localhost:8000/docs
streamlit run dashboard/app.py  # em outro terminal: http://localhost:8501
```

Opções do seed: `--months 12`, `--reset` (recria os dados do usuário demo).

## 🐳 Docker

```bash
cp .env.example .env     # defina SECRET_KEY e POSTGRES_PASSWORD
docker compose up --build                              # desenvolvimento (hot-reload da API)
docker compose -f docker-compose.yml up -d --build     # estável (sem override)
```

Com `APP_ENV=production` a API **recusa subir** com `SECRET_KEY` fraca. Gere uma com:
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 🔌 Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/register`, `/auth/login` | Cadastro e login (JWT) |
| GET/POST | `/auth/me`, `/auth/change-password` | Perfil e troca de senha |
| GET/POST | `/transactions/` | Lista (filtros: `q`, `type`, `category`, `start_date`, `end_date`, `min_amount`, `max_amount`, `sort_by`, `order`, `skip`, `limit`) / cria |
| GET/PUT/DELETE | `/transactions/{id}` | Consulta, atualiza, exclui |
| GET | `/transactions/export`, `/transactions/export.xlsx` | CSV / Excel com os mesmos filtros |
| POST | `/transactions/import` | Importa CSV (`descricao;valor;categoria;tipo;data`) |
| GET | `/transactions/categories` | Categorias do usuário |
| GET/PUT/DELETE | `/budgets/`, `/budgets/{categoria}` | Orçamentos mensais |
| GET | `/analytics/overview?days=30` | **Tudo do dashboard em uma chamada** (com cache) |
| GET | `/analytics/report.pdf?days=30` | Relatório executivo em PDF |
| GET/PUT | `/admin/users`, `/admin/users/{id}/role`, `/admin/users/{id}/active` | Somente admin |
| GET | `/analytics/summary`, `/by-category`, `/timeseries`, `/monthly`, `/weekday`, `/top-expenses`, `/forecast`, `/anomalies`, `/recurring`, `/budgets` | Análises individuais |

## 🧪 Testes

```bash
pytest                        # tudo
pytest tests/test_analytics_core.py tests/test_csv_io.py   # só o núcleo (não precisa subir a API)
ruff check .
```

## 🗄️ Migrações (Alembic)

```bash
alembic upgrade head                 # banco novo: cria tudo
alembic stamp 0001 && alembic upgrade head   # banco criado pela v1 (já tem users/transactions)
alembic revision --autogenerate -m "minha mudança"   # novas migrações
```

No Docker a API roda `alembic upgrade head` ao subir (`AUTO_CREATE_TABLES=false`). Faça **backup do banco** antes de migrar um banco com dados reais: a 0002 converte `amount` para `NUMERIC(12,2)`.

## 👥 Perfis

O primeiro admin nasce por configuração: `ADMIN_USERNAMES=meu_usuario` no `.env` (vale no cadastro). Depois ele promove/rebaixa pelos endpoints `/admin`. Usuários desativados perdem o acesso na hora (inclusive tokens já emitidos).

## ⚠️ Notas

- **Previsão** é uma estimativa estatística simples, não um modelo de ML nem uma garantia.
- O limitador de login é em memória (por processo): com vários workers cada um conta separado. O cache usa Redis quando `REDIS_URL` está definido.
- `.env` nunca deve ir para o repositório.

## 📄 Licença

MIT.
