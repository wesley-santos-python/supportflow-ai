# 🎫 SupportFlow AI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Web%20API-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-+%20Tailwind-3366CC?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?style=for-the-badge&logo=google&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)

**Sistema inteligente de gestão de tickets de suporte com IA generativa**

[📋 Funcionalidades](#-funcionalidades) •
[🚀 Instalação](#-instalação) •
[⚙️ Configuração](#️-configuração) •
[📖 Uso](#-uso) •
[🏗️ Arquitetura](#️-arquitetura)

</div>

---

## 📋 Funcionalidades

- 📧 **Integração IMAP** - Busca automática de e-mails não lidos (Gmail/Outlook), com dedupe antes da IA
- 🤖 **Análise com IA** - Classifica urgência, categoria e gera respostas usando Google Gemini
- 🏷️ **Classificação Automática** - Urgência (Alta/Média/Baixa) e categoria (Técnico/Financeiro/Logística/Outros)
- 📊 **Painel de KPIs** - Métricas em tempo real (total, urgência, status) no topo do dashboard
- 🔎 **Busca e Filtros** - Por assunto/remetente, categoria, urgência e status
- 🔄 **Gestão de Status** - Marque tickets como Pendente / Em Andamento / Resolvido
- 💾 **Persistência configurável** - PostgreSQL por padrão (SQLite/MySQL via `.env`), com SQLAlchemy
- 🖥️ **Dashboard Web Moderno** - Interface dark mode com FastAPI + HTMX + Tailwind (sem build de Node)
- 🔌 **API JSON** - Endpoints reutilizáveis (`/api/tickets`, `/api/stats`) e exportação
- 📋 **Sugestão de Respostas** - IA gera respostas editáveis prontas para copiar

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- Conta Google Cloud com API Gemini habilitada
- Conta de e-mail com acesso IMAP habilitado
- Docker (opcional, para subir o PostgreSQL rapidamente)

### Passos

```bash
# Clone o repositório
git clone https://github.com/wesley-santos-python/supportflow-ai.git
cd supportflow-ai

# Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate     # Windows

# Instale as dependências
pip install -r requirements.txt

# Suba o banco PostgreSQL (via Docker)
docker compose up -d
```

---

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha:

```env
# Banco de dados (PostgreSQL por padrão; troque a URL para SQLite/MySQL sem mexer no código)
DATABASE_URL=postgresql+psycopg://supportflow:supportflow@localhost:5432/supportflow

# Credenciais de E-mail (Gmail)
EMAIL_USER=seu-email@gmail.com
EMAIL_PASS=sua-senha-de-app

# API Google Gemini
AI_API_KEY=sua-chave-api-gemini
AI_MODEL=gemini-2.5-flash-lite
```

### 2. Configurar Gmail

Para usar com Gmail, você precisa:

1. Ativar **Verificação em 2 etapas** na sua conta Google
2. Gerar uma **Senha de App** em [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Usar essa senha no `EMAIL_PASS`

### 3. Obter API Key do Gemini

1. Acesse [Google AI Studio](https://aistudio.google.com/)
2. Crie uma nova API Key
3. Copie para o `AI_API_KEY`

---

## 📖 Uso

### Executar o Dashboard

```bash
python main.py
```

Acesse a interface web em **http://127.0.0.1:8000**.

### Executar Testes

```bash
pytest tests/ -v
```

### API JSON

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/tickets` | Lista tickets (filtros: `search`, `categoria`, `urgencia`, `status`, `limit`, `offset`) |
| `GET /api/stats` | Métricas agregadas (KPIs) |
| `GET /export.json` | Download de todos os tickets em JSON |
| `GET /health` | Health check |

---

## 🗄️ Trocar Banco de Dados

O backend é definido pela variável `DATABASE_URL` no `.env` — **sem editar código**:

```env
# PostgreSQL (padrão)
DATABASE_URL=postgresql+psycopg://usuario:senha@servidor:5432/nome_banco

# SQLite (arquivo local)
DATABASE_URL=sqlite:///./support_flow.db

# MySQL (requer: pip install pymysql)
DATABASE_URL=mysql+pymysql://usuario:senha@servidor:3306/nome_banco
```

O SQLAlchemy cria as tabelas automaticamente na primeira execução.

---

## 🏗️ Arquitetura

```
supportflow-ai/
├── main.py                    # Ponto de entrada (servidor uvicorn)
├── docker-compose.yml         # PostgreSQL para desenvolvimento
├── src/
│   ├── config.py              # ⚙️ Configuração via .env (pydantic-settings)
│   ├── core/                  # 🧠 Lógica de negócio
│   │   ├── ai_engine.py       # Integração Google Gemini (retry + truncamento)
│   │   ├── automation.py      # Orquestrador (dedupe antes da IA)
│   │   └── email_service.py   # Cliente IMAP (marca lidos em lote)
│   ├── data/                  # 💾 Camada de dados
│   │   ├── db.py              # Sessões + repositório SQLAlchemy
│   │   └── models.py          # Modelo ORM Ticket
│   ├── web/                   # 🎨 Interface web
│   │   ├── app.py            # App FastAPI (rotas HTMX + API JSON)
│   │   ├── templates/        # Páginas e fragmentos Jinja2
│   │   └── static/           # CSS + JS (toasts, clipboard)
│   ├── utils/                 # 🔧 Utilitários
│   │   └── logger.py          # Logging configurável (LOG_LEVEL)
│   └── exceptions.py          # Exceções customizadas
└── tests/                     # 🧪 Testes automatizados
    ├── test_ai_engine.py
    ├── test_automation.py
    ├── test_db.py
    ├── test_email_service.py
    └── test_web.py
```

### Fluxo de Dados

```mermaid
flowchart LR
    A[📧 E-mail IMAP] --> B[EmailService]
    B --> C[SupportController]
    C --> D[🤖 AIService]
    D --> E[Gemini API]
    E --> D
    D --> C
    C --> F[💾 PostgreSQL]
    F --> G[⚡ FastAPI]
    G --> H[🖥️ Dashboard HTMX]
```

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|------------|-----|
| **FastAPI** | Framework web / API (ASGI) |
| **HTMX + Tailwind** | Frontend interativo server-rendered (sem build de Node) |
| **Jinja2** | Templates HTML |
| **SQLAlchemy** | ORM para banco de dados |
| **PostgreSQL** | Banco de dados (configurável via `.env`) |
| **pydantic-settings** | Configuração por variáveis de ambiente |
| **Google Gemini** | IA generativa para análise |
| **imap-tools** | Cliente IMAP moderno |
| **pytest** | Framework de testes |

---

## 📊 Modelo de Dados

### Ticket

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | Integer | Chave primária auto-incremento |
| `uid` | String | ID único do e-mail (IMAP) |
| `sender` | String | Remetente do e-mail |
| `subject` | String | Assunto do e-mail |
| `body` | Text | Corpo do e-mail |
| `urgencia` | String | Alta / Média / Baixa |
| `categoria` | String | Técnico / Financeiro / Logística / Outros |
| `resumo` | Text | Resumo gerado pela IA |
| `resposta_sugerida` | Text | Resposta gerada pela IA |
| `status` | String | Pendente / Em Andamento / Resolvido |
| `created_at` | DateTime | Data de criação |
| `updated_at` | DateTime | Data da última atualização |

---

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie sua branch de feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## 🔒 Segurança e Privacidade

### Seus dados estão seguros

| Aspecto | Garantia |
|---------|----------|
| **Armazenamento** | 100% local no seu computador |
| **Banco de dados** | Roda na sua infraestrutura (PostgreSQL local/Docker ou SQLite); não vai para servidores de terceiros |
| **Credenciais** | Armazenadas apenas no seu arquivo `.env` |
| **Código** | 100% open-source e auditável |

### Sobre a IA (Google Gemini)

> **A IA NÃO armazena seus dados!**

- O Google Gemini recebe apenas o **texto do e-mail** para análise
- A análise é feita em tempo real e **descartada imediatamente** após
- A Google confirma que dados via API **não são usados para treinar modelos**
- Veja a [Política de Privacidade da API Gemini](https://ai.google.dev/gemini-api/terms)

### O que a Floatech pode ver?

**NADA.** 🔐

- Não temos acesso aos seus e-mails
- Não temos acesso ao seu banco de dados
- Não temos acesso às suas credenciais
- O sistema roda **100% na sua máquina**

### Recomendações de Segurança

1. **Nunca compartilhe** seu arquivo `.env`
2. **Use senhas de app** em vez da senha principal do e-mail
3. **Mantenha o sistema atualizado** com as últimas versões

---

## 📄 Direitos Autorais e Licença

**© 2026 Floatech - Weslei Santos. Todos os direitos reservados.**

Este projeto é parte de um portfólio profissional e propriedade intelectual de seu autor.
O código-fonte é disponibilizado publicamente apenas para fins de **demonstração e avaliação técnica**.

❌ É proibido o uso comercial, cópia, modificação ou redistribuição sem autorização prévia por escrito.

Para consultas sobre licenciamento ou contratação, entre em contato via LinkedIn.

---

<div align="center">

**Desenvolvido com ❤️ por Weslei Santos**

</div>
