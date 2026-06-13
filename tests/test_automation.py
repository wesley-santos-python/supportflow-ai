"""
Testes para o orquestrador de sincronização (SupportController).
"""
import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.data.db as db_module
from src.data.db import create_ticket
from src.data.models import Base


@pytest.fixture
def memory_db():
    """Aponta o SessionLocal do módulo para um SQLite em memória."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    original_engine, original_session = db_module.engine, db_module.SessionLocal
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    yield db_module.SessionLocal
    db_module.engine, db_module.SessionLocal = original_engine, original_session


def _build_controller(emails, analysis):
    """Cria um SupportController com EmailService e AIService mockados."""
    with patch("src.core.automation.EmailService") as MockEmail, patch(
        "src.core.automation.AIService"
    ) as MockAI:
        email = MockEmail.return_value
        email.fetch_unread_emails.return_value = emails
        email.mark_as_read_bulk.return_value = True
        ai = MockAI.return_value
        ai.analyze_ticket.return_value = analysis
        from src.core.automation import SupportController

        controller = SupportController()
    return controller, email, ai


ANALYSIS = {
    "urgencia": "Alta",
    "categoria": "Técnico",
    "resumo": "Resumo",
    "resposta_sugerida": "Resposta",
}


def test_run_sync_processes_new_emails(memory_db):
    emails = [
        {"id": "u1", "sender": "a@x.com", "subject": "S1", "body": "corpo 1"},
        {"id": "u2", "sender": "b@x.com", "subject": "S2", "body": "corpo 2"},
    ]
    controller, email, ai = _build_controller(emails, ANALYSIS)

    processed = controller.run_sync()

    assert processed == 2
    assert ai.analyze_ticket.call_count == 2
    email.mark_as_read_bulk.assert_called_once_with(["u1", "u2"])


def test_run_sync_skips_empty_body(memory_db):
    emails = [{"id": "u1", "sender": "a@x.com", "subject": "S", "body": ""}]
    controller, email, ai = _build_controller(emails, ANALYSIS)

    assert controller.run_sync() == 0
    ai.analyze_ticket.assert_not_called()


def test_run_sync_dedupe_before_ai(memory_db):
    """E-mails já processados não devem disparar a IA novamente."""
    with memory_db() as s:
        create_ticket(
            s, {"uid": "u1", "sender": "a@x.com", "subject": "S", "body": "b"}
        )

    emails = [{"id": "u1", "sender": "a@x.com", "subject": "S", "body": "b"}]
    controller, email, ai = _build_controller(emails, ANALYSIS)

    controller.run_sync()

    ai.analyze_ticket.assert_not_called()  # dedupe evitou a chamada de IA


def test_run_sync_no_emails(memory_db):
    controller, email, ai = _build_controller([], ANALYSIS)
    assert controller.run_sync() == 0
    email.mark_as_read_bulk.assert_not_called()
