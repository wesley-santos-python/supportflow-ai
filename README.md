# 🎫 SupportFlow AI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Web%20SaaS-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini%203.1%20Flash%20Lite-AI-4285F4?style=for-the-badge&logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

**SaaS de gestão inteligente de tickets de suporte com IA generativa**

_by **Floatech** — Weslei Santos_

[📋 Funcionalidades](#-funcionalidades) •
[🚀 Instalação](#-instalação) •
[⚙️ Configuração](#️-configuração) •
[🏗️ Arquitetura](#️-arquitetura)

</div>

---

## 📋 Funcionalidades

- 👥 **SaaS multi-cliente** — login por e-mail+senha; cada cliente vê apenas os próprios dados e conecta o próprio e-mail
- 🔐 **Segurança** — senhas com hash bcrypt; credenciais de e-mail dos clientes criptografadas (Fernet/AES)
- 🌐 **Interface web moderna** — dashboard responsivo em dark mode, com cards de tickets
- 🤖 **Análise com IA (Gemini 3.1 Flash Lite)** — classifica urgência, categoria, resumo e gera resposta sugerida
- 📊 **Painel de análise com gráficos** — distribuição por categoria, urgência, status e volume por dia
- 🔍 **Filtros avançados** — por categoria, urgência, status e busca textual
- ✉️ **Resposta pelo próprio SaaS** — envie a sugestão da IA, reescreva com instruções ou edite e anexe arquivos
- 📅 **Agendamento de respostas** — programe o envio de e-mails para um horário futuro
- ⏰ **Lembretes / follow-ups** — crie lembretes associados (ou não) a um ticket
- 📎 **Anexos organizados** — download opcional sob demanda (estrutura por ticket), visualização e impressão pelo sistema
- 📄 **Relatórios** — exportação em JSON/CSV e relatório imprimível (PDF via navegador)
- ⚙️ **Configuração rápida por cliente** — cada cliente conecta o próprio e-mail pela interface, sem editar arquivos
- 🔄 **Atualização automática** — sincronização de e-mails a cada 2 minutos (configurável)
- 📱 **Pronto para WhatsApp** — resumo de e-mails urgentes preparado para envio ao responsável

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- Conta Google com API Gemini habilitada
- Conta de e-mail com acesso IMAP/SMTP (Gmail/Outlook)

### Passos

```bash
# Clone o repositório
git clone https://github.com/wesley-santos-python/supportflow-ai.git
cd supportflow-ai

# Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows

# Instale as dependências
pip install -r requirements.txt
```

---

## ⚙️ Configuração

A configuração é dividida em dois níveis:

### 1. Global — do dono da plataforma (`.env` / variáveis de ambiente)

A IA é fornecida pela plataforma (você paga o Gemini para todos os clientes).

```env
# Obrigatório em produção: assina sessões e criptografa segredos dos clientes
SECRET_KEY=use-um-segredo-forte-e-unico   # ex.: openssl rand -hex 32

# IA global (a plataforma fornece)
AI_API_KEY=sua-chave-api-gemini
GEMINI_MODEL=gemini-3.1-flash-lite

# Intervalo de sincronização do scheduler (vale para todos)
SYNC_INTERVAL_MINUTES=2
```

> **Gemini:** obtenha a chave no [Google AI Studio](https://aistudio.google.com/).

### 2. Por cliente — pela interface web (após login)

Cada cliente cria sua conta, faz login e conecta o **próprio e-mail** em
**Configurações** (provedor, e-mail e senha de app). A senha é criptografada
antes de ser salva. Nenhuma credencial de cliente fica em `.env`.

> **Gmail:** o cliente deve ativar a verificação em 2 etapas e gerar uma
> [Senha de App](https://myaccount.google.com/apppasswords).

---

## 📖 Uso

### Iniciar o SaaS

```bash
python main.py
# ou, com reload em desenvolvimento:
uvicorn src.web.app:app --reload
```

Acesse **http://127.0.0.1:8000** no navegador. Crie sua conta em **/register**,
faça login e conecte seu e-mail em **Configurações**.

| Página | Descrição |
|--------|-----------|
| **/register · /login** | Cadastro e acesso do cliente |
| **Dashboard** | Cards de tickets, filtros, sincronização e resposta |
| **Análises** | Gráficos por categoria, urgência, status e volume diário |
| **Lembretes & Agenda** | Lembretes e respostas agendadas |
| **Relatórios** | Exportação JSON/CSV e relatório imprimível |
| **Configurações** | Conexão de e-mail e WhatsApp (por cliente) |

### Executar testes

```bash
pytest tests/ -v
```

---

## 🗄️ Trocar Banco de Dados

Por padrão usa **SQLite**. Para MySQL/PostgreSQL, basta exportar `DATABASE_URL`:

```bash
# MySQL
export DATABASE_URL="mysql+pymysql://usuario:senha@servidor:3306/nome_banco"
# PostgreSQL
export DATABASE_URL="postgresql://usuario:senha@servidor:5432/nome_banco"
```

O SQLAlchemy cuida da criação das tabelas automaticamente.

---

## ☁️ Deploy no Railway

O projeto já vem pronto para o [Railway](https://railway.app) (Procfile +
`railway.json`, bind em `0.0.0.0:$PORT` e suporte a PostgreSQL).

1. **Crie o projeto** no Railway a partir deste repositório
   (_New Project → Deploy from GitHub repo_).
2. **Variáveis de ambiente** (aba _Variables_) — apenas as **globais**:
   ```env
   SECRET_KEY=use-um-segredo-forte-e-unico   # ex.: openssl rand -hex 32
   AI_API_KEY=sua-chave-gemini
   GEMINI_MODEL=gemini-3.1-flash-lite
   SYNC_INTERVAL_MINUTES=2
   ```
   > As credenciais de e-mail **não** vão aqui — cada cliente conecta o próprio
   > e-mail pela interface após o login. A porta é injetada pelo Railway
   > (`PORT`) — não defina manualmente.
3. **Banco de dados (recomendado):** adicione um **PostgreSQL** (_New → Database_).
   O Railway cria a variável `DATABASE_URL` automaticamente e o app a utiliza
   (o SQLite local é efêmero em container e se perde a cada deploy).
4. **Deploy:** o Railway detecta o Python via Nixpacks, instala o
   `requirements.txt` e sobe com o `startCommand` do `railway.json`.
5. Acesse a URL pública, crie sua conta em **/register** e conecte o e-mail.

> O agendador (sincronização a cada 2 min) roda no mesmo processo web — ideal
> para uma única instância. Para múltiplas réplicas, isole o scheduler em um
> serviço _worker_ separado.

---

## 🏗️ Arquitetura

```
supportflow-ai/
├── main.py                     # Ponto de entrada (Uvicorn)
├── src/
│   ├── config.py               # ⚙️ Configuração global (DB + .env + padrões)
│   ├── security.py             # 🔐 Hash de senha (bcrypt) + cripto de segredos (Fernet)
│   ├── user_config.py          # ⚙️ Configuração por cliente (multi-tenant)
│   ├── core/                   # 🧠 Lógica de negócio
│   │   ├── ai_engine.py        # Integração Gemini (análise/reescrita/resumo)
│   │   ├── automation.py       # Orquestrador (e-mail → IA → banco, respostas)
│   │   ├── email_service.py    # Cliente IMAP (leitura) + SMTP (envio)
│   │   ├── attachments.py      # Download organizado de anexos
│   │   ├── scheduler.py        # APScheduler (sync 2min, agendamentos, lembretes)
│   │   ├── reports.py          # Geração de relatórios (JSON/CSV/HTML)
│   │   └── notifications.py    # Resumo de urgentes (WhatsApp — preparado)
│   ├── data/                   # 💾 Camada de dados
│   │   ├── db.py               # CRUD escopado por cliente, analytics, migrações
│   │   └── models.py           # Users, Settings, Tickets, Anexos, Lembretes, Agendados
│   ├── web/                    # 🎨 Camada web (FastAPI)
│   │   ├── app.py              # App factory + sessão + lifecycle + scheduler
│   │   ├── auth.py             # Sessão e dependências de autenticação
│   │   ├── routes/             # Rotas de auth, páginas e API
│   │   ├── templates/          # Templates Jinja2 (inclui login/registro)
│   │   └── static/             # CSS e JS
│   ├── utils/logger.py         # 🔧 Logging
│   └── exceptions.py           # Exceções customizadas
└── tests/                      # 🧪 Testes automatizados
```

### Fluxo de Dados

```mermaid
flowchart LR
    A[📧 E-mail IMAP] --> B[EmailService]
    B --> C[SupportController]
    C --> D[🤖 AIService · Gemini]
    D --> C
    C --> E[💾 Banco de Dados]
    E --> F[🌐 FastAPI]
    F --> G[🖥️ Dashboard Web]
    H[⏱️ Scheduler 2min] --> C
    C --> I[✉️ SMTP / 📅 Agendados]
    E --> J[📱 Resumo urgentes → WhatsApp]
```

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|------------|-----|
| **FastAPI + Uvicorn** | Framework web assíncrono (SaaS) |
| **Jinja2** | Templates server-side |
| **Chart.js** | Gráficos do painel de análise |
| **APScheduler** | Tarefas em background (sync, agendamentos, lembretes) |
| **SQLAlchemy** | ORM (SQLite/MySQL/PostgreSQL) |
| **Google Gemini 3.1 Flash Lite** | IA generativa para análise |
| **imap-tools / smtplib** | Leitura e envio de e-mail |
| **pytest** | Testes automatizados |

---

## 📱 Integração com WhatsApp (preparada)

O envio do resumo de e-mails urgentes ao responsável já está estruturado em
`src/core/notifications.py`. Ao habilitar nas configurações, o sistema gera o
resumo via IA e o despacha. A integração com um provedor real (Twilio / Meta
Cloud API) é um ponto de extensão isolado em `WhatsAppNotifier._send`, sem
impacto no restante do sistema.

---

## 🔒 Segurança e Privacidade

- **Local-first:** o sistema roda 100% na sua máquina; o banco é local.
- **Credenciais:** ficam no `.env` ou no banco local — nunca saem do ambiente.
- **IA:** o Gemini recebe apenas o texto do e-mail para análise; dados via API
  [não são usados para treino](https://ai.google.dev/gemini-api/terms).
- **Anexos:** só são baixados quando você solicita (ou se habilitar o download
  automático).

---

## 📄 Direitos Autorais e Licença

**© 2026 Floatech - Weslei Santos. Todos os direitos reservados.**

Projeto de portfólio profissional. Código disponibilizado apenas para fins de
demonstração e avaliação técnica. É proibido o uso comercial, cópia,
modificação ou redistribuição sem autorização prévia por escrito.

---

<div align="center">

**Desenvolvido com ❤️ por Weslei Santos · Floatech**

</div>
