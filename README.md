# 📊 Dashboard Analytics

**API RESTful com FastAPI e dashboard interativo com Streamlit para análise de dados financeiros e métricas de e-commerce.**

O **Dashboard Analytics** é um projeto de portfólio que combina engenharia de dados, desenvolvimento backend e visualização de informações, permitindo gerenciar transações e acompanhar indicadores por meio de gráficos e análises interativas.

## ✨ Funcionalidades

- 🔐 **Autenticação JWT** com senhas protegidas por hash bcrypt.
- 💳 **CRUD de transações** para cadastrar, consultar, atualizar e excluir registros.
- 📈 **Análise de dados** com Pandas e NumPy.
- 🗂️ **Análise por categoria** para identificar padrões de receitas e despesas.
- 📅 **Séries temporais** para acompanhar a evolução dos indicadores.
- 💰 **Resumo financeiro** com receitas, despesas e saldo.
- 🏆 **Ranking de despesas** para identificar os maiores gastos.
- 📊 **Dashboard interativo** com Streamlit e Plotly.
- 🐳 **Containerização** com Docker e Docker Compose.
- 🧪 **Testes automatizados** com pytest.
- 📚 **Documentação da API** com Swagger UI e ReDoc.

## 🛠️ Stack Tecnológica

| Camada | Tecnologias |
|---|---|
| Backend | Python, FastAPI |
| ORM e validação | SQLAlchemy, Pydantic |
| Banco de dados | SQLite, PostgreSQL |
| Análise de dados | Pandas, NumPy |
| Frontend | Streamlit, Plotly |
| Autenticação | JWT, python-jose, passlib[bcrypt] |
| Testes | pytest |
| DevOps | Docker, Docker Compose |
| Documentação | Swagger UI, ReDoc |

## 📁 Estrutura do Projeto

```text
dashboard-analytics/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── analytics.py
│   └── routers/
├── dashboard/
│   └── app.py
├── tests/
├── seed_data.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🚀 Como Executar Localmente

### Pré-requisitos

- Python 3.10 ou superior
- pip
- Git

### 1. Clone o repositório

```bash
git clone https://github.com/SEU-USUARIO/dashboard-analytics.git
cd dashboard-analytics
```

Substitua `SEU-USUARIO` pelo seu nome de usuário do GitHub e ajuste a URL conforme o repositório criado.

### 2. Crie e ative o ambiente virtual

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux/macOS:**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

No Windows PowerShell, utilize:

```powershell
Copy-Item .env.example .env
```

Configure as variáveis necessárias no arquivo `.env`, incluindo a URL do banco de dados e a chave secreta utilizada na autenticação.

### 5. Gere os dados de demonstração

```bash
python seed_data.py
```

O script disponibiliza dados de exemplo e cria o usuário de demonstração:

- **Usuário:** `demo`
- **Senha:** `demo123`

> **Atenção:** utilize essas credenciais somente em ambiente local de demonstração. Nunca publique senhas reais ou chaves secretas no repositório.

### 6. Inicie a API

```bash
uvicorn app.main:app --reload --port 8000
```

Acesse a documentação interativa:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 7. Inicie o dashboard

Em outro terminal, com o ambiente virtual ativado, execute:

```bash
streamlit run dashboard/app.py
```

Acesse o dashboard em:

http://localhost:8501

## 🐳 Executando com Docker

Com o Docker e o Docker Compose instalados, execute:

```bash
docker compose up --build
```

Serviços disponíveis:

| Serviço | URL |
|---|---|
| API REST | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Dashboard | http://localhost:8501 |

Para encerrar os serviços:

```bash
docker compose down
```

## 🔌 Endpoints da API

### Autenticação

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/auth/register` | Cadastra um usuário |
| `POST` | `/auth/login` | Autentica e retorna um JWT |
| `GET` | `/auth/me` | Retorna os dados do usuário autenticado |

### Transações

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/transactions/` | Cria uma transação |
| `GET` | `/transactions/` | Lista transações |
| `GET` | `/transactions/{id}` | Consulta uma transação |
| `PUT` | `/transactions/{id}` | Atualiza uma transação |
| `DELETE` | `/transactions/{id}` | Exclui uma transação |

### Analytics

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/analytics/summary` | Retorna receitas, despesas e saldo |
| `GET` | `/analytics/by-category` | Agrupa valores por categoria |
| `GET` | `/analytics/timeseries` | Retorna séries temporais de receitas e despesas |
| `GET` | `/analytics/top-expenses` | Lista as maiores despesas |

> Os endpoints e seus parâmetros devem ser conferidos na documentação Swagger da aplicação.

## 🧪 Executando os Testes

Execute a suíte de testes com:

```bash
pytest -v
```

Para obter um relatório de cobertura, caso `pytest-cov` esteja instalado:

```bash
pytest --cov=app --cov-report=term-missing
```

## 🗄️ Configuração do PostgreSQL

Por padrão, o projeto pode utilizar SQLite no ambiente de desenvolvimento. Para utilizar PostgreSQL, configure a variável `DATABASE_URL` no arquivo `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dashboard
```

O driver `psycopg2-binary` deve estar instalado para conexões PostgreSQL síncronas.

> **Importante:** a URL e o driver precisam ser compatíveis com a configuração do SQLAlchemy utilizada no projeto. Se a aplicação utilizar conexões assíncronas, será necessário configurar um driver assíncrono, como `asyncpg`.

## 🎯 Objetivos do Projeto

Este projeto demonstra conhecimentos práticos em:

- Desenvolvimento de APIs REST com Python e FastAPI.
- Modelagem de dados e integração com bancos relacionais.
- Autenticação e controle de acesso com JWT.
- Manipulação e análise de dados com Pandas e NumPy.
- Criação de dashboards e visualizações com Plotly.
- Testes automatizados e organização de código.
- Containerização e configuração de ambientes com Docker.

## 📄 Licença

Este projeto está licenciado sob a licença MIT.

Consulte o arquivo `LICENSE` para obter os termos completos.
