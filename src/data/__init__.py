"""
Módulo de dados do SupportFlow AI.

Contém modelos ORM e funções de acesso ao banco de dados.
"""
from .db import (
    SessionLocal,
    create_ticket,
    delete_ticket,
    get_db,
    get_stats,
    get_ticket,
    init_db,
    list_tickets,
    session_scope,
    set_status,
    ticket_exists,
)
from .models import Base, Ticket

__all__ = [
    "SessionLocal",
    "create_ticket",
    "delete_ticket",
    "get_db",
    "get_stats",
    "get_ticket",
    "init_db",
    "list_tickets",
    "session_scope",
    "set_status",
    "ticket_exists",
    "Base",
    "Ticket",
]
