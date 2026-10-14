# 📊 Dashboard Analytics

**Plataforma de análise financeira desenvolvida com Python, FastAPI e Streamlit.**

Aplicação que combina uma API RESTful, persistência relacional e análise de dados para gerenciar transações financeiras, acompanhar orçamentos, identificar padrões de despesas e gerar previsões e relatórios.

O projeto foi desenvolvido para explorar boas práticas de **backend, segurança, arquitetura modular, testes automatizados, análise estatística e containerização**.

## ✨ Funcionalidades

### 🔐 Autenticação e segurança

- Autenticação baseada em JWT com PyJWT.
- Hash de senhas com bcrypt.
- Cadastro, login, consulta de perfil e alteração de senha.
- Controle de acesso baseado em perfis: `user`, `viewer` e `admin`.
- Proteção contra tentativas excessivas de login, com resposta HTTP `429`.
- Revogação de tokens após alteração de senha.
- Verificação de e-mail e recuperação de senha.
- Exportação e exclusão dos dados da conta, incluindo recursos relacionados à LGPD.

### ⚙️ Desenvolvimento Backend e API REST

- API desenvolvida com FastAPI e Uvicorn.
- Operações CRUD para receitas, despesas, categorias e orçamentos.
- Validação de dados e separação entre modelos, schemas, regras de negócio e rotas.
- Filtros por texto, categoria, tipo, período e faixa de valores.
- Paginação e ordenação de transações.
- Importação de arquivos CSV e OFX com opção de prevenção de duplicidades.
- Exportação de dados em CSV e Excel.
- Endpoints para análises financeiras, previsões e relatórios.
- Documentação interativa da API com Swagger UI e ReDoc.

### 🗄️ Persistência e modelagem de dados

- PostgreSQL como banco de dados relacional.
- SQLAlchemy 2 para mapeamento objeto-relacional (ORM).
- Alembic para versionamento e aplicação de migrações.
- Armazenamento de valores monetários com `NUMERIC(12,2)`.
- Índices para apoiar consultas e restrições de unicidade.
- Modelagem de usuários, transações, orçamentos e demais recursos financeiros.
- Isolamento dos dados financeiros por usuário autenticado.

### 📈 Análise de dados e estatística

- Processamento e análise de dados com Pandas e NumPy.
- Resumos financeiros e comparativos entre períodos.
- Análise de receitas, despesas, saldo acumulado e taxa de poupança.
- Séries temporais com médias móveis.
- Agrupamento de despesas por categoria e dia da semana.
- Identificação das maiores despesas.
- Detecção de gastos atípicos com z-score modificado e histórico individual de transações.
- Identificação de despesas recorrentes.
- Projeções de despesas e saldo para os próximos 30 dias, utilizando nível, tendência amortecida e sazonalidade semanal.

### 🎯 Orçamentos e planejamento financeiro

- Definição de limites mensais por categoria.
- Acompanhamento do consumo dos orçamentos.
- Projeção de gastos até o final do mês.
- Identificação de categorias com risco de ultrapassar o limite.
- Contas e carteiras com cálculo de saldo.
- Metas de poupança com acompanhamento de progresso e prazo.
- Alertas de orçamento por e-mail e webhook.

### 📊 Dashboard e relatórios

- Dashboard interativo desenvolvido com Streamlit e Plotly.
- Cinco áreas de visualização: visão geral, análises, orçamentos, transações e insights.
- Gráficos e indicadores para exploração dos dados financeiros.
- Edição de transações diretamente na interface.
- Insights gerados a partir dos dados disponíveis.
- Exportação de relatórios em Excel.
- Geração de relatório executivo em PDF.

## 🏗️ Arquitetura

A aplicação utiliza uma arquitetura modular que separa a interface de visualização, a API, as regras de negócio, a persistência e os componentes analíticos.

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

### Decisões de arquitetura

- **Separação de responsabilidades:** rotas, autenticação, persistência, análises e relatórios são organizados em módulos distintos.
- **Núcleo analítico desacoplado:** cálculos financeiros e regras estatísticas podem ser testados sem iniciar a API ou acessar o banco de dados.
- **Persistência versionada:** Alembic mantém o histórico de alterações do esquema do banco.
- **Endpoint consolidado:** `/analytics/overview` reúne dados utilizados pelas diferentes áreas do dashboard, reduzindo chamadas repetidas.
- **Cache com invalidação:** resultados são armazenados por usuário durante 30 segundos, com suporte a memória ou Redis conforme a configuração.
- **Precisão monetária:** valores financeiros são persistidos com `NUMERIC(12,2)`, evitando depender de tipos de ponto flutuante para armazenar dinheiro.
- **Configuração por ambiente:** credenciais, chave secreta, conexão com banco e parâmetros operacionais são definidos por variáveis de ambiente.

## 🛠️ Tecnologias

| Categoria | Tecnologias |
|---|---|
| Linguagem | Python |
| Backend e API | FastAPI, Uvicorn |
| Banco de dados | PostgreSQL |
| ORM e migrações | SQLAlchemy 2, Alembic |
| Autenticação | PyJWT, bcrypt |
| Análise de dados | Pandas, NumPy |
| Visualização | Streamlit, Plotly |
| Cache | Redis |
| Relatórios | OpenPyXL, ReportLab |
| Testes | pytest |
| Qualidade de código | Ruff |
| Infraestrutura | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Versionamento | Git, GitHub |

## 🚀 Como executar localmente

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

Substitua `SEU_USUARIO` pelo usuário correto e ajuste o nome do repositório, se necessário.

### 2. Crie e ative o ambiente virtual

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

### 4. Configure o ambiente

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS**

```bash
cp .env.example .env
```

Configure a URL do banco de dados, a `SECRET_KEY` e as demais variáveis exigidas pela aplicação no arquivo `.env`.

Não publique credenciais, chaves secretas ou arquivos `.env` no repositório.

### 5. Inicialize os dados de demonstração

```bash
python seed_data.py
```

O script prepara dados demonstrativos com histórico financeiro para testes e exploração do dashboard.

Para gerar um histórico de 12 meses:

```bash
python seed_data.py --months 12
```

Para recriar os dados da demonstração:

```bash
python seed_data.py --reset
```

As credenciais demonstrativas devem ser utilizadas somente em ambiente local.

### 6. Aplique as migrações

```bash
alembic upgrade head
```

Faça backup antes de aplicar migrações em bancos que contenham dados importantes.

### 7. Inicie a API

```bash
uvicorn app.main:app --reload
```

Endpoints locais:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Healthcheck: `http://localhost:8000/health`

### 8. Inicie o dashboard

Em outro terminal, com o ambiente virtual ativado:

```bash
streamlit run dashboard/app.py
```

Acesse `http://localhost:8501`.

## 🐳 Executando com Docker

Com Docker e Docker Compose instalados, configure o ambiente:

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Defina os valores necessários, incluindo `SECRET_KEY` e `POSTGRES_PASSWORD`.

Inicie os serviços:

```bash
docker compose up --build
```

Para iniciar em segundo plano:

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

A disponibilidade de cada serviço depende da configuração dos arquivos Compose. Em produção, utilize credenciais seguras e não utilize a chave secreta de exemplo.

## 🧪 Testes e qualidade de código

Execute a suíte de testes:

```bash
pytest
```

Execute os testes do núcleo analítico e da importação CSV:

```bash
pytest tests/test_analytics_core.py tests/test_csv_io.py
```

Verifique a qualidade do código:

```bash
ruff check .
```

O projeto utiliza testes automatizados para validar regras analíticas, processamento de arquivos CSV e endpoints da aplicação. A integração contínua é configurada com GitHub Actions.

## 🔌 Principais endpoints

| Método | Endpoint | Responsabilidade |
|---|---|---|
| POST | `/auth/register` | Cadastro de usuário |
| POST | `/auth/login` | Autenticação e emissão de JWT |
| GET | `/auth/me` | Perfil do usuário autenticado |
| GET | `/transactions/` | Consulta de transações |
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

A API também oferece endpoints de análises por categoria, séries temporais, comparativos mensais, despesas recorrentes e gerenciamento de orçamentos.

Consulte o Swagger UI para verificar os parâmetros, os schemas das requisições e as respostas disponíveis.

## 🔒 Perfis de acesso

| Perfil | Responsabilidade |
|---|---|
| `user` | Gerenciamento dos próprios dados e recursos permitidos |
| `viewer` | Acesso somente para leitura |
| `admin` | Gerenciamento de usuários e permissões administrativas |

O cadastro público não concede privilégios administrativos. A criação e a promoção de administradores são realizadas por comandos de administração da aplicação.

## ⚙️ Desempenho e confiabilidade

- Cache por usuário com TTL de 30 segundos.
- Invalidação do cache após operações de escrita.
- Suporte a Redis para compartilhamento do cache entre instâncias.
- Paginação de transações.
- Controle de tentativas excessivas de login.
- Healthcheck para acompanhamento da disponibilidade da API.
- Execução do container da API sem privilégios de root.
- Tratamento de datas com base em `APP_TIMEZONE`, cujo padrão é `America/Sao_Paulo`.

Quando houver múltiplos workers, a configuração de cache e limitação de tentativas deve considerar o compartilhamento de estado. O comportamento depende da disponibilidade e da configuração do Redis.

## 📌 Limitações conhecidas

- As previsões financeiras são estimativas estatísticas baseadas no histórico disponível, não garantias de resultados futuros.
- A detecção de anomalias depende da quantidade e da qualidade dos dados históricos.
- A sessão persistente do dashboard utiliza um cookie acessível por JavaScript, conforme a implementação atual.
- A aplicação exige configuração adequada de credenciais, variáveis de ambiente e migrações antes de ser utilizada em produção.

## 📄 Licença

Este projeto está licenciado sob a licença [MIT](LICENSE).

---

**Desenvolvido com Python, FastAPI e SQLAlchemy para explorar desenvolvimento backend, APIs REST, modelagem relacional, autenticação, análise de dados, testes automatizados e boas práticas de engenharia de software.**
