# 📊 Dashboard Analytics

**Plataforma de análise financeira desenvolvida com Python, FastAPI, PostgreSQL e Streamlit.**

Aplicação que integra uma API RESTful, persistência relacional e análise de dados para gerenciamento de transações, controle de orçamentos, identificação de despesas atípicas e geração de previsões e relatórios financeiros.

O projeto demonstra a aplicação prática de conceitos de **desenvolvimento backend, autenticação, modelagem de dados, arquitetura modular, testes automatizados e containerização**.

## 🚀 Principais funcionalidades

### Backend e API REST

- API desenvolvida com FastAPI e Uvicorn.
- Operações CRUD para receitas, despesas e orçamentos.
- Validação de dados e organização modular das rotas.
- Filtros, paginação e ordenação de transações.
- Importação de arquivos CSV e OFX com prevenção opcional de duplicidades.
- Exportação de dados em CSV e Excel.
- Endpoints para análises financeiras, previsões e relatórios.
- Documentação interativa com Swagger UI e ReDoc.

### Segurança e autenticação

- Autenticação baseada em JWT com PyJWT.
- Proteção de senhas com hash bcrypt.
- Cadastro, login, alteração de senha e consulta de perfil.
- Controle de acesso baseado em funções: `user`, `viewer` e `admin`.
- Limitação de tentativas de login.
- Revogação de tokens após alteração de senha.
- Recuperação de senha, verificação de e-mail e gerenciamento de dados pessoais.
- Exportação e exclusão de dados da conta, com recursos relacionados à LGPD.

### Banco de dados e persistência

- PostgreSQL como banco de dados relacional.
- SQLAlchemy 2 para mapeamento objeto-relacional (ORM).
- Alembic para versionamento e aplicação de migrações.
- Valores monetários armazenados com `NUMERIC(12,2)`.
- Índices e restrições de unicidade para integridade dos dados.
- Separação dos dados financeiros por usuário autenticado.

### Análise de dados

- Processamento de dados com Pandas e NumPy.
- Indicadores financeiros e comparativos entre períodos.
- Análises por categoria, dia da semana e maiores despesas.
- Séries temporais com saldo acumulado e médias móveis.
- Detecção de gastos atípicos usando z-score modificado e histórico individual.
- Identificação de despesas recorrentes.
- Projeção de despesas e saldo para os próximos 30 dias, considerando nível, tendência amortecida e sazonalidade semanal.

### Dashboard e relatórios

- Interface interativa com Streamlit e Plotly.
- Cinco áreas: visão geral, análises, orçamentos, transações e insights.
- Acompanhamento de limites mensais e projeção de gastos.
- Contas, carteiras e metas de poupança.
- Alertas de orçamento por e-mail e webhook.
- Exportação de relatórios em Excel e geração de relatórios executivos em PDF.

## 🛠️ Stack tecnológica

| Categoria | Tecnologias |
|---|---|
| Linguagem | Python |
| API e backend | FastAPI, Uvicorn |
| Banco de dados | PostgreSQL |
| ORM e migrações | SQLAlchemy 2, Alembic |
| Autenticação | PyJWT, bcrypt |
| Análise de dados | Pandas, NumPy |
| Dashboard e gráficos | Streamlit, Plotly |
| Cache | Redis |
| Relatórios | OpenPyXL, ReportLab |
| Testes | pytest |
| Qualidade de código | Ruff |
| Infraestrutura | Docker, Docker Compose |
| CI/CD | GitHub Actions |

## 🏗️ Arquitetura

A aplicação separa as responsabilidades entre API, regras de negócio, persistência, processamento analítico, relatórios e interface de visualização.

```text
dashboard-analytics/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── security.py
│   ├── analytics_core.py
│   ├── analytics.py
│   ├── csv_io.py
│   ├── reports.py
│   ├── cache.py
│   └── routers/
│       ├── auth.py
│       ├── transactions.py
│       ├── budgets.py
│       ├── analytics.py
│       └── admin.py
├── migrations/
├── dashboard/
│   └── app.py
├── tests/
├── seed_data.py
├── requirements-dev.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

### Decisões técnicas

- **Separação de responsabilidades:** os módulos de autenticação, rotas, persistência, análises e relatórios possuem responsabilidades distintas.
- **Núcleo analítico desacoplado:** cálculos financeiros podem ser testados sem inicializar a API ou acessar o banco de dados.
- **Migrações versionadas:** Alembic mantém o histórico de alterações no esquema relacional.
- **Precisão financeira:** `NUMERIC(12,2)` evita depender de ponto flutuante para armazenar valores monetários.
- **Endpoint consolidado:** `/analytics/overview` reúne os dados utilizados pelas diferentes áreas do dashboard, reduzindo chamadas repetidas.
- **Cache com invalidação:** os dados são armazenados por usuário durante 30 segundos, utilizando memória ou Redis conforme a configuração.
- **Configuração por ambiente:** credenciais e parâmetros operacionais são definidos por variáveis de ambiente.

## 💻 Como executar localmente

### Pré-requisitos

- Python 3.11 ou superior, conforme as dependências do projeto.
- pip.
- PostgreSQL ou Docker.
- Git.

### 1. Clone o repositório

```bash
git clone https://github.com/SEU_USUARIO/dashboard-analytics.git
cd dashboard-analytics
```

Substitua `SEU_USUARIO` pelo nome de usuário correto e ajuste o nome do repositório, se necessário.

### 2. Crie o ambiente virtual

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux/macOS**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements-dev.txt
```

### 4. Configure as variáveis de ambiente

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS**

```bash
cp .env.example .env
```

Configure a conexão com o banco de dados, a `SECRET_KEY` e as demais variáveis necessárias no arquivo `.env`.

Nunca publique credenciais ou chaves secretas no repositório.

### 5. Prepare o banco e os dados demonstrativos

Aplique as migrações:

```bash
alembic upgrade head
```

Inicialize os dados de demonstração:

```bash
python seed_data.py
```

Para gerar 12 meses de histórico:

```bash
python seed_data.py --months 12
```

Para recriar os dados demonstrativos:

```bash
python seed_data.py --reset
```

Utilize as credenciais de demonstração somente no ambiente local.

### 6. Inicie a API

```bash
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`.

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Healthcheck: `http://localhost:8000/health`

### 7. Inicie o dashboard

Em outro terminal, com o ambiente virtual ativado:

```bash
streamlit run dashboard/app.py
```

Acesse `http://localhost:8501`.

## 🐳 Executando com Docker

Configure o arquivo `.env` a partir do exemplo e defina as variáveis necessárias, incluindo `SECRET_KEY` e `POSTGRES_PASSWORD`.

Inicie os serviços:

```bash
docker compose up --build
```

Para executar em segundo plano:

```bash
docker compose -f docker-compose.yml up -d --build
```

Acompanhe os logs:

```bash
docker compose logs -f
```

Encerre os serviços:

```bash
docker compose down
```

A disponibilidade dos serviços depende da configuração dos arquivos Compose. Em produção, utilize chaves fortes e credenciais próprias.

## 🔌 Principais endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/auth/register` | Cadastro de usuário |
| POST | `/auth/login` | Autenticação e emissão de JWT |
| GET | `/auth/me` | Consulta do perfil autenticado |
| POST | `/auth/change-password` | Alteração de senha |
| GET | `/transactions/` | Listagem de transações |
| POST | `/transactions/` | Criação de transações |
| PUT | `/transactions/{id}` | Atualização de transações |
| DELETE | `/transactions/{id}` | Exclusão de transações |
| POST | `/transactions/import` | Importação de transações |
| GET | `/transactions/export.xlsx` | Exportação para Excel |
| GET | `/budgets/` | Consulta de orçamentos |
| GET | `/analytics/overview` | Dados consolidados do dashboard |
| GET | `/analytics/forecast` | Projeções financeiras |
| GET | `/analytics/anomalies` | Detecção de gastos atípicos |
| GET | `/analytics/report.pdf` | Relatório executivo em PDF |
| GET | `/admin/users` | Administração de usuários |

A API também disponibiliza análises por categoria, séries temporais, comparativos mensais, despesas recorrentes e gerenciamento de orçamentos.

Consulte o Swagger UI para conferir os parâmetros, schemas e respostas de cada endpoint.

## 🧪 Testes e qualidade de código

Execute os testes automatizados:

```bash
pytest
```

Execute os testes do núcleo analítico e do processamento CSV:

```bash
pytest tests/test_analytics_core.py tests/test_csv_io.py
```

Verifique a qualidade estática do código:

```bash
ruff check .
```

Os testes contemplam regras analíticas, processamento de arquivos CSV e endpoints da aplicação. O projeto também utiliza GitHub Actions para integração contínua.

## ⚙️ Desempenho e confiabilidade

- Cache por usuário com TTL de 30 segundos.
- Invalidação após operações de escrita.
- Suporte a Redis para compartilhamento do cache entre instâncias.
- Paginação de transações.
- Limitação de tentativas de login.
- Healthchecks e execução da API em container sem privilégios de root.
- Tratamento de datas conforme `APP_TIMEZONE`, com padrão `America/Sao_Paulo`.

Quando há múltiplos workers, a configuração do cache e do controle de tentativas deve considerar o compartilhamento de estado. Sem Redis, o cache em memória não é compartilhado entre processos.

## 📌 Limitações

- As previsões são estimativas estatísticas e não garantem resultados financeiros futuros.
- A detecção de anomalias depende da quantidade e da qualidade do histórico disponível.
- A sessão persistente do dashboard utiliza um cookie acessível por JavaScript na implementação atual.
- A utilização em produção exige configuração adequada de credenciais, variáveis de ambiente, banco de dados e migrações.

## 📄 Licença

Este projeto está licenciado sob a licença [MIT](LICENSE).

---

**Desenvolvido com Python para demonstrar conhecimentos práticos em desenvolvimento backend, APIs REST, persistência relacional, autenticação, análise de dados, testes automatizados e arquitetura de software.**
