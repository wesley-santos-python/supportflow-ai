"""
Módulo de dados do SupportFlow AI.

Contém modelos ORM e funções de acesso ao banco de dados.
"""
from .db import (
    init_db, 
    save_ticket, 
    get_all_tickets, 
    get_ticket_by_id, 
    update_ticket_status,
    delete_ticket,
    get_session,
    SessionLocal
)
from .models import Ticket, Base

__all__ = [
    'init_db', 
    'save_ticket', 
    'get_all_tickets', 
    'get_ticket_by_id', 
    'update_ticket_status',
    'delete_ticket',
    'get_session',
    'SessionLocal',
    'Ticket', 
    'Base'
]
