# 🎫 SupportFlow AI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/Flet-UI%20Framework-02569B?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?style=for-the-badge&logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

**Sistema inteligente de gestão de tickets de suporte com IA generativa**

[📋 Funcionalidades](#-funcionalidades) •
[🚀 Instalação](#-instalação) •
[⚙️ Configuração](#️-configuração) •
[📖 Uso](#-uso) •
[🏗️ Arquitetura](#️-arquitetura)

</div>

---

## 📋 Funcionalidades

- 📧 **Integração IMAP** - Busca automática de e-mails não lidos (Gmail/Outlook)
- 🤖 **Análise com IA** - Classifica urgência, categoria e gera respostas usando Google Gemini
- 🏷️ **Classificação Automática** - Urgência (Alta/Média/Baixa) e categoria (Técnico/Financeiro/Logística)
- 💾 **Persistência SQLite** - Armazenamento local estruturado com SQLAlchemy
- 🖥️ **Dashboard Moderno** - Interface dark mode com Flet framework
- 📋 **Sugestão de Respostas** - IA gera respostas prontas para copiar/enviar

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- Conta Google Cloud com API Gemini habilitada
- Conta de e-mail com acesso IMAP habilitado

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
```

---

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Credenciais de E-mail (Gmail)
EMAIL_USER=seu-email@gmail.com
EMAIL_PASS=sua-senha-de-app

# API Google Gemini
AI_API_KEY=sua-chave-api-gemini
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

O dashboard será aberto automaticamente no navegador.

### Executar Testes

```bash
pytest tests/ -v
```

### Exportar Dados

Clique no botão **Exportar JSON** no dashboard para baixar todos os tickets em formato JSON.

---

## 🗄️ Trocar Banco de Dados

Por padrão, o SupportFlow AI usa **SQLite** (arquivo local). Para usar **MySQL** ou **PostgreSQL**:

### 1. Instale o driver

```bash
# MySQL
pip install pymysql

# PostgreSQL
pip install psycopg2-binary
```

### 2. Altere `src/data/db.py`

```python
# De (SQLite local):
DATABASE_URL = "sqlite:///./support_flow.db"

# Para MySQL:
DATABASE_URL = "mysql+pymysql://usuario:senha@servidor:3306/nome_banco"

# Para PostgreSQL:
DATABASE_URL = "postgresql://usuario:senha@servidor:5432/nome_banco"
```

O SQLAlchemy cuida de toda migração automaticamente!

---

## 🏗️ Arquitetura

```
supportflow-ai/
├── main.py                    # Ponto de entrada
├── src/
│   ├── core/                  # 🧠 Lógica de negócio
│   │   ├── ai_engine.py       # Integração Google Gemini
│   │   ├── automation.py      # Orquestrador de fluxo
│   │   └── email_service.py   # Cliente IMAP
│   ├── data/                  # 💾 Camada de dados
│   │   ├── db.py              # Funções CRUD SQLAlchemy
│   │   └── models.py          # Modelo ORM Ticket
│   ├── ui/                    # 🎨 Interface do usuário
│   │   ├── dashboard.py       # Dashboard principal
│   │   └── components.py      # Componentes reutilizáveis
│   ├── utils/                 # 🔧 Utilitários
│   │   └── logger.py          # Sistema de logging
│   └── exceptions.py          # Exceções customizadas
└── tests/                     # 🧪 Testes automatizados
    ├── test_ai_engine.py
    ├── test_db.py
    └── test_email_service.py
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
    C --> F[💾 Database]
    F --> G[🖥️ Dashboard]
```

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|------------|-----|
| **Flet** | Framework UI Python (Flutter-based) |
| **SQLAlchemy** | ORM para banco de dados |
| **SQLite** | Banco de dados local |
| **Google Gemini** | IA generativa para análise |
| **imap-tools** | Cliente IMAP moderno |
| **python-dotenv** | Gerenciamento de variáveis de ambiente |
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
| **Banco de dados** | SQLite local (não vai para nenhum servidor) |
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
