"""
Configuração compartilhada de testes.

Garante que toda a suíte rode com SQLite em memória (sem depender do PostgreSQL),
definindo DATABASE_URL antes de qualquer import dos módulos da aplicação.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
