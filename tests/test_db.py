"""
Testes para o módulo de banco de dados (API baseada em sessão).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.data.db import (
    create_ticket,
    delete_ticket,
    get_stats,
    get_ticket,
    list_tickets,
    set_status,
    ticket_exists,
)
from src.data.models import Base


@pytest.fixture
def db():
    """Fornece uma sessão isolada com SQLite em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _ticket(uid="uid-1", **extra):
    data = {
        "uid": uid,
        "sender": "cliente@email.com",
        "subject": "Problema com pedido",
        "body": "Meu pedido não chegou",
        "urgencia": "Alta",
        "categoria": "Logística",
        "resumo": "Cliente aguardando pedido",
        "resposta_sugerida": "Vamos verificar.",
    }
    data.update(extra)
    return data


class TestDatabase:
    def test_create_ticket_success(self, db):
        ticket = create_ticket(db, _ticket())
        assert ticket is not None
        assert ticket.sender == "cliente@email.com"
        assert ticket.status == "Pendente"  # default
        assert ticket.created_at is not None

    def test_create_duplicate_uid_returns_none(self, db):
        assert create_ticket(db, _ticket(uid="dup")) is not None
        assert create_ticket(db, _ticket(uid="dup")) is None
        assert len(list_tickets(db)) == 1

    def test_ticket_exists(self, db):
        assert ticket_exists(db, "uid-x") is False
        create_ticket(db, _ticket(uid="uid-x"))
        assert ticket_exists(db, "uid-x") is True

    def test_get_ticket(self, db):
        created = create_ticket(db, _ticket(uid="uid-get"))
        found = get_ticket(db, created.id)
        assert found is not None and found.uid == "uid-get"
        assert get_ticket(db, 99999) is None

    def test_set_status(self, db):
        created = create_ticket(db, _ticket(uid="uid-st"))
        assert set_status(db, created.id, "Resolvido") is True
        assert get_ticket(db, created.id).status == "Resolvido"
        assert set_status(db, 99999, "Resolvido") is False

    def test_delete_ticket(self, db):
        created = create_ticket(db, _ticket(uid="uid-del"))
        assert delete_ticket(db, created.id) is True
        assert len(list_tickets(db)) == 0
        assert delete_ticket(db, 99999) is False

    def test_list_filters_and_search(self, db):
        create_ticket(db, _ticket(uid="a", categoria="Técnico", urgencia="Baixa", subject="Login falhou"))
        create_ticket(db, _ticket(uid="b", categoria="Financeiro", urgencia="Alta", subject="Cobrança"))

        assert len(list_tickets(db, categoria="Técnico")) == 1
        assert len(list_tickets(db, urgencia="Alta")) == 1
        assert len(list_tickets(db, search="login")) == 1
        assert len(list_tickets(db, search="inexistente")) == 0

    def test_list_orders_by_urgency(self, db):
        create_ticket(db, _ticket(uid="low", urgencia="Baixa"))
        create_ticket(db, _ticket(uid="high", urgencia="Alta"))
        tickets = list_tickets(db)
        assert tickets[0].urgencia == "Alta"

    def test_get_stats(self, db):
        create_ticket(db, _ticket(uid="s1", urgencia="Alta"))
        create_ticket(db, _ticket(uid="s2", urgencia="Baixa"))
        stats = get_stats(db)
        assert stats["total"] == 2
        assert stats["alta"] == 1
        assert stats["pendente"] == 2
