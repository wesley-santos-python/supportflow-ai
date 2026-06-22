"""
Testes para as funções estendidas do banco de dados:
filtros, lembretes, respostas agendadas, configurações e analytics.
"""
from datetime import datetime, timedelta

import pytest

TEST_DB_URL = "sqlite:///:memory:"


class TestExtendedDB:
    """Testes para as novas funções de src.data.db."""

    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Configura banco em memória antes de cada teste."""
        import src.data.db as db_module
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.data.models import Base

        engine = create_engine(TEST_DB_URL)
        db_module.engine = engine
        db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        yield
        Base.metadata.drop_all(bind=engine)

    def _ticket(self, **overrides):
        data = {
            "uid": "u1",
            "sender": "cliente@x.com",
            "subject": "Erro no login",
            "body": "Não consigo entrar",
            "urgencia": "Alta",
            "categoria": "Técnico",
            "resumo": "Cliente sem acesso",
        }
        data.update(overrides)
        return data

    def test_query_tickets_filters(self):
        from src.data.db import query_tickets, save_ticket

        save_ticket(self._ticket(uid="a", categoria="Técnico", urgencia="Alta"))
        save_ticket(self._ticket(uid="b", categoria="Financeiro", urgencia="Baixa"))

        assert len(query_tickets(categoria="Técnico")) == 1
        assert len(query_tickets(urgencia="Baixa")) == 1
        assert len(query_tickets(search="login")) >= 1
        assert len(query_tickets()) == 2

    def test_settings_roundtrip(self):
        from src.data.db import get_setting, set_setting

        assert get_setting("FOO") is None
        set_setting("FOO", "bar")
        assert get_setting("FOO") == "bar"
        set_setting("FOO", "baz")
        assert get_setting("FOO") == "baz"

    def test_reminders_lifecycle(self):
        from src.data.db import (
            create_reminder,
            due_reminders,
            list_reminders,
            set_reminder_done,
        )

        past = datetime.now() - timedelta(minutes=5)
        rid = create_reminder({"title": "Retornar", "remind_at": past})
        assert rid is not None
        assert len(list_reminders()) == 1
        assert len(due_reminders()) == 1

        set_reminder_done(rid, True)
        assert len(due_reminders()) == 0

    def test_scheduled_replies_due(self):
        from src.data.db import (
            create_scheduled_reply,
            due_scheduled_replies,
            save_ticket,
            update_scheduled_reply_status,
        )
        from src.data.models import ScheduledReply

        ticket_id = save_ticket(self._ticket())
        past = datetime.now() - timedelta(minutes=1)
        rid = create_scheduled_reply(
            {
                "ticket_id": ticket_id,
                "to_email": "cliente@x.com",
                "subject": "Re: Erro",
                "body": "Olá",
                "scheduled_for": past,
                "status": ScheduledReply.STATUS_PENDING,
            }
        )
        assert len(due_scheduled_replies()) == 1
        update_scheduled_reply_status(rid, ScheduledReply.STATUS_SENT)
        assert len(due_scheduled_replies()) == 0

    def test_analytics_summary(self):
        from src.data.db import analytics_summary, save_ticket

        save_ticket(self._ticket(uid="a", urgencia="Alta", categoria="Técnico"))
        save_ticket(self._ticket(uid="b", urgencia="Baixa", categoria="Financeiro"))

        summary = analytics_summary()
        assert summary["total"] == 2
        assert summary["urgentes"] == 1
        assert summary["by_category"]["Técnico"] == 1
        assert "by_day" in summary

    def test_attachment_registration(self):
        from src.data.db import add_attachment, get_attachment, mark_attachment_downloaded, save_ticket

        ticket_id = save_ticket(self._ticket())
        aid = add_attachment(
            {"ticket_id": ticket_id, "filename": "nota.pdf", "content_type": "application/pdf", "size": 10}
        )
        assert aid is not None
        att = get_attachment(aid)
        assert att.filename == "nota.pdf"
        assert att.downloaded is False

        mark_attachment_downloaded(aid, "/tmp/nota.pdf")
        assert get_attachment(aid).downloaded is True
