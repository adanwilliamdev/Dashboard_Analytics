# 📊 Dashboard Analytics

**Plataforma de análise de finanças pessoais com Python, FastAPI e Streamlit.**

API RESTful e dashboard interativo para gerenciamento de transações, controle de orçamentos, análise de despesas, previsão financeira e geração de relatórios.

O projeto combina **desenvolvimento backend, engenharia de dados, análise estatística e visualização de dados** em uma aplicação modular, com autenticação, testes automatizados e suporte a Docker.

---

## ✨ Funcionalidades

### 🔐 Autenticação e segurança
- Autenticação baseada em JWT com PyJWT e senhas protegidas com bcrypt.
- Cadastro, login, consulta de perfil e alteração de senha.
- Política de senhas com mínimo de 8 caracteres.
- Proteção contra tentativas excessivas de login, com resposta HTTP `429`.
- Controle de acesso baseado em perfis: `user`, `viewer` e `admin`.
- Gerenciamento e desativação de contas administrativas.

### 💳 Gerenciamento de transações
- CRUD completo de receitas e despesas.
- Filtros por texto, tipo, categoria, período e faixa de valores.
- Ordenação e paginação de resultados.
- Importação e exportação de transações em CSV, incluindo valores no formato brasileiro.
- Exportação de dados para Excel.

### 🎯 Controle de orçamentos
- Definição de limites mensais por categoria.
- Acompanhamento do consumo dos orçamentos.
- Projeção de gastos até o final do mês.
- Identificação de categorias com risco de ultrapassar o limite.

### 📈 Análise financeira
- Resumo financeiro com comparação entre períodos.
- Cálculo da taxa de poupança.
- Séries temporais diárias com saldo acumulado e média móvel.
- Comparativos mensais de receitas e despesas.
- Análise de gastos por categoria e dia da semana.
- Identificação das maiores despesas.

### 🔮 Previsão e detecção de anomalias
- Projeção de despesas e saldo para os próximos 30 dias.
- Modelo estatístico com nível, tendência amortecida e sazonalidade semanal.
- Intervalo de previsão aproximado de 80%.
- Detecção de gastos atípicos usando z-score modificado e histórico individual de transações.
- Identificação de despesas recorrentes, como assinaturas e contas mensais.

### 💡 Dashboard e relatórios
- Interface interativa desenvolvida com Streamlit e Plotly.
- Cinco abas: visão geral, análises, orçamentos, transações e insights.
- Carregamento consolidado dos dados do dashboard por meio do endpoint `/analytics/overview`.
- Insights automáticos gerados a partir dos dados financeiros.
- Relatórios Excel com resumo, transações, categorias e comparativo mensal.
- Relatório executivo em PDF para o período selecionado.

### ⚡ Infraestrutura e qualidade
- API RESTful com FastAPI.
- Persistência em banco de dados relacional.
- Migrações versionadas com Alembic.
- Valores monetários armazenados em `NUMERIC(12,2)`.
- Cache por usuário com TTL de 30 segundos, utilizando memória ou Redis.
- Testes automatizados com pytest.
- Padronização e análise estática de código com Ruff.
- Integração contínua com GitHub Actions.
- Containerização com Docker e Docker Compose.
- Healthchecks e execução da API sem privilégios de root.

---

## 🛠️ Tecnologias

| Categoria | Tecnologias |
|---|---|
| Linguagem | Python |
| API e backend | FastAPI, Uvicorn |
| Dados e análise | Pandas, NumPy |
| Dashboard e gráficos | Streamlit, Plotly |
| Banco de dados | PostgreSQL |
| ORM e migrações | SQLAlchemy 2, Alembic |
| Autenticação | PyJWT, bcrypt |
| Cache | Redis |
| Relatórios | OpenPyXL, ReportLab |
| Testes e qualidade | pytest, Ruff |
| Infraestrutura | Docker, Docker Compose |
| CI/CD | GitHub Actions |

---

## 🏗️ Arquitetura

A aplicação separa as responsabilidades entre API, núcleo analítico, persistência, geração de relatórios e interface de visualização.

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

### Organização dos componentes

- **API:** autenticação, validação, regras de negócio e endpoints REST.
- **Núcleo analítico:** cálculos estatísticos desacoplados do banco, facilitando testes unitários.
- **Persistência:** modelos relacionais, consultas e migrações de esquema.
- **Dashboard:** visualização interativa e consumo consolidado dos dados da API.
- **Relatórios:** geração de arquivos Excel e PDF.
- **Cache:** redução de consultas repetidas e invalidação após operações de escrita.
- **Testes:** validação das regras analíticas, importação de CSV e endpoints.

---

## 🚀 Como executar localmente

### Pré-requisitos

- Python 3.11 ou superior, conforme as dependências do projeto.
- pip.
- PostgreSQL, caso não utilize Docker.
- Git.

### 1. Clone o repositório

```bash
git clone https://github.com/SEU_USUARIO/dashboard-analytics.git
cd dashboard-analytics
```

Substitua `SEU_USUARIO` pelo seu nome de usuário do GitHub e ajuste o nome do repositório, se necessário.

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

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux/macOS
cp .env.example .env
```

Configure a URL do banco de dados, a chave secreta da aplicação e as demais variáveis necessárias no arquivo `.env`.

**Importante:** não compartilhe credenciais, chaves secretas ou arquivos `.env` no repositório.

### 5. Inicialize os dados de demonstração

```bash
python seed_data.py
```

O script cria dados demonstrativos para o usuário:

| Campo | Valor |
|---|---|
| Usuário | `demo` |
| Senha | `demo1234` |
| Dados iniciais | 6 meses de histórico |

O script também aceita opções para personalizar a quantidade de dados:

```bash
python seed_data.py --months 12
```

Para recriar os dados do usuário de demonstração:

```bash
python seed_data.py --reset
```

Utilize as credenciais demonstrativas apenas no ambiente local.

### 6. Inicie a API

```bash
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`.

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Healthcheck:** http://localhost:8000/health

### 7. Inicie o dashboard

Em outro terminal, com o ambiente virtual ativado:

```bash
streamlit run dashboard/app.py
```

Acesse o dashboard em `http://localhost:8501`.

---

## 🐳 Executando com Docker

Certifique-se de ter Docker e Docker Compose instalados.

### 1. Configure o ambiente

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Defina os valores necessários, incluindo `SECRET_KEY` e `POSTGRES_PASSWORD`.

### 2. Inicie os serviços

**Desenvolvimento, com hot reload da API:**

```bash
docker compose up --build
```

**Execução estável, sem o override de desenvolvimento:**

```bash
docker compose -f docker-compose.yml up -d --build
```

A disponibilidade dos serviços depende da configuração definida nos arquivos Compose.

Para acompanhar os logs:

```bash
docker compose logs -f
```

Para encerrar os serviços:

```bash
docker compose down
```

### Segurança em produção

Com `APP_ENV=production`, a aplicação rejeita uma `SECRET_KEY` fraca.

Gere uma chave segura com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configure a chave gerada nas variáveis de ambiente. Não utilize a chave de exemplo em produção.

---

## 🔌 Principais endpoints

### Autenticação

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/auth/register` | Cadastro de usuário |
| POST | `/auth/login` | Autenticação e emissão de JWT |
| GET | `/auth/me` | Consulta do perfil autenticado |
| POST | `/auth/change-password` | Alteração de senha |

### Transações

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/transactions/` | Lista transações com filtros |
| POST | `/transactions/` | Cria uma transação |
| GET | `/transactions/{id}` | Consulta uma transação |
| PUT | `/transactions/{id}` | Atualiza uma transação |
| DELETE | `/transactions/{id}` | Exclui uma transação |
| GET | `/transactions/export` | Exporta transações em CSV |
| GET | `/transactions/export.xlsx` | Exporta transações em Excel |
| POST | `/transactions/import` | Importa transações por CSV |
| GET | `/transactions/categories` | Lista categorias do usuário |

**Filtros disponíveis:** `q`, `type`, `category`, `start_date`, `end_date`, `min_amount`, `max_amount`, `sort_by`, `order`, `skip` e `limit`.

### Orçamentos

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/budgets/` | Consulta orçamentos |
| PUT | `/budgets/{categoria}` | Cria ou atualiza o limite por categoria |
| DELETE | `/budgets/{categoria}` | Remove um orçamento |

### Análises e relatórios

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/analytics/overview?days=30` | Dados consolidados do dashboard |
| GET | `/analytics/summary` | Resumo financeiro |
| GET | `/analytics/by-category` | Gastos por categoria |
| GET | `/analytics/timeseries` | Série temporal |
| GET | `/analytics/monthly` | Comparativo mensal |
| GET | `/analytics/weekday` | Perfil de gastos por dia da semana |
| GET | `/analytics/top-expenses` | Maiores despesas |
| GET | `/analytics/forecast` | Previsão financeira |
| GET | `/analytics/anomalies` | Detecção de gastos atípicos |
| GET | `/analytics/recurring` | Despesas recorrentes |
| GET | `/analytics/budgets` | Análise de orçamentos |
| GET | `/analytics/report.pdf?days=30` | Relatório executivo em PDF |

### Administração

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/admin/users` | Lista usuários |
| PUT | `/admin/users/{id}/role` | Altera o perfil de acesso |
| PUT | `/admin/users/{id}/active` | Ativa ou desativa uma conta |

Os endpoints administrativos exigem permissões adequadas. Consulte a documentação Swagger para verificar os parâmetros, os corpos das requisições e os códigos de resposta.

---

## 🗄️ Migrações de banco de dados

O projeto utiliza Alembic para versionar alterações no esquema.

**Banco novo:**

```bash
alembic upgrade head
```

**Banco legado da versão 1**, que já contém as tabelas `users` e `transactions`:

```bash
alembic stamp 0001
alembic upgrade head
```

**Criar uma nova migração:**

```bash
alembic revision --autogenerate -m "minha mudança"
```

A migração `0002` inclui alterações relacionadas a orçamentos, perfis de acesso e precisão monetária, convertendo `amount` para `NUMERIC(12,2)`.

A migração `0003` adiciona `users.token_version` (revogação de tokens ao trocar a senha) e um índice único em `lower(username)`. Se já existirem usernames que colidem ignorando maiúsculas (ex.: `Ana` e `ana`), a migração **para** listando-os: renomeie ou remova um dos lados e rode `alembic upgrade head` novamente.

Faça backup antes de migrar bancos com dados importantes. Em produção, confirme o estado do esquema antes de aplicar qualquer migração.

---

## 👥 Perfis de acesso

| Perfil | Permissões |
|---|---|
| `user` | Gerenciamento das próprias transações e recursos permitidos |
| `viewer` | Acesso somente para leitura |
| `admin` | Gerenciamento de usuários e permissões administrativas |

O cadastro público **nunca** concede o perfil `admin`. O administrador é criado no servidor, pela linha de comando:

```bash
# local
python -m app.cli create-admin meu_usuario meu@email.com     # pede a senha no terminal

# Docker
docker compose exec api python -m app.cli create-admin meu_usuario meu@email.com

# promover alguém que já se cadastrou
python -m app.cli promote meu_usuario
```

A senha também pode vir da variável `ADMIN_PASSWORD` (automação). A variável `ADMIN_USERNAMES` foi **descontinuada e é ignorada** (a API registra um aviso na subida se ela estiver definida): ela permitia que qualquer pessoa tomasse o username reservado antes do administrador.

Contas desativadas perdem o acesso, inclusive por meio de tokens anteriormente emitidos. Trocar a senha também invalida todos os tokens já emitidos.

**Usernames não diferenciam maiúsculas e minúsculas** (`Ana` e `ana` são a mesma conta; novos cadastros são gravados em minúsculas). **Senhas aceitam no máximo 72 bytes** (limite do bcrypt; caracteres acentuados ocupam mais de 1 byte): acima disso o cadastro e a troca de senha são rejeitados em vez de truncar em silêncio.

---

## 🧪 Testes e qualidade de código

Execute todos os testes:

```bash
pytest
```

Execute apenas os testes do núcleo analítico e do parser CSV:

```bash
pytest tests/test_analytics_core.py tests/test_csv_io.py
```

Verifique a qualidade do código:

```bash
ruff check .
```

O núcleo analítico é separado da camada de persistência, permitindo testar cálculos e regras financeiras sem precisar iniciar a API para esses testes.

O projeto também conta com integração contínua via GitHub Actions.

---

## ⚙️ Cache e desempenho

O endpoint `/analytics/overview` consolida os dados necessários para as cinco abas do dashboard, reduzindo chamadas repetidas à API.

- Cache por usuário com TTL de 30 segundos.
- Invalidação do cache após operações de escrita.
- Armazenamento em memória ou Redis, conforme `REDIS_URL`.
- Paginação para consultas de transações.
- Índices e tipos monetários adequados à persistência financeira.

**Observação:** o cache em memória não é compartilhado entre processos. Com `WEB_CONCURRENCY` maior que 1 e **sem** `REDIS_URL`, a API desativa o cache (e registra um aviso), para que a invalidação após uma escrita nunca deixe outro worker servindo dado velho. O `docker compose` já sobe com Redis.

### Fuso horário

"Hoje", a janela de dias, o mês do orçamento, a previsão e a data padrão de novas transações seguem `APP_TIMEZONE` (padrão `America/Sao_Paulo`), e não o UTC do servidor. O banco guarda datetimes *naive* que representam o horário de parede nesse fuso; datas recebidas **com** fuso (`...-03:00`, `Z`) são convertidas para `APP_TIMEZONE` ao gravar e ao filtrar. A API e o dashboard devem usar o mesmo valor. *Ao atualizar:* transações já gravadas por clientes que enviavam datas com fuso foram guardadas em UTC e podem aparecer algumas horas adiantadas; as criadas pelo dashboard (data sem fuso) não são afetadas.

### Logs e proxy reverso

Os logs `dashboard.*` (acesso, cache, segurança) são configurados na subida; ajuste com `LOG_LEVEL`. Atrás de um proxy reverso, defina `FORWARDED_ALLOW_IPS` com o IP/CIDR do proxy para que o limitador de login veja o IP real do cliente (sem isso, todos aparecem com o IP do proxy).

---

## 📌 Limitações e considerações

- **Previsões:** estimativas estatísticas baseadas no histórico, sem garantia de resultados futuros.
- **Anomalias:** a detecção depende da quantidade e da qualidade dos dados históricos disponíveis.
- **Rate limiting:** com `REDIS_URL` o contador de tentativas de login é compartilhado entre workers (janela fixa). Sem Redis ele é por processo, e se o Redis cair o login continua protegido por um contador local.
- **Sessão do dashboard:** o login sobrevive ao F5 por um cookie `SameSite=Strict` (`Secure` em https) gravado via JavaScript, pois o Streamlit não grava cookies pelo servidor; por isso ele é legível por scripts da página. Defina `REMEMBER_SESSION=false` para desativar.
- **Cache:** Redis permite compartilhar o cache entre instâncias quando corretamente configurado.
- **Segurança:** credenciais de demonstração são destinadas exclusivamente ao ambiente local.
- **Migrações:** bancos com dados reais devem ser respaldados antes de alterações estruturais.

---

## 📄 Licença

Este projeto está licenciado sob a licença [MIT](LICENSE).

---

**Desenvolvido com Python para explorar APIs REST, análise de dados, estatística aplicada, visualização e boas práticas de engenharia de software.**
