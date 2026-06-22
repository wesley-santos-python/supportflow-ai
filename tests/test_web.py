"""
Testes de integração da camada web (FastAPI).

Usa um banco em memória e não inicia o agendador real.
"""
import pytest


@pytest.fixture
def client():
    """Cliente de teste com banco em memória e scheduler desligado."""
    from unittest.mock import patch

    import src.data.db as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from src.data.models import Base

    # StaticPool mantém uma única conexão in-memory compartilhada entre as
    # threads do pool de execução do FastAPI/Starlette.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from fastapi.testclient import TestClient
    from src.web.app import app

    # Evita iniciar threads de agendamento durante os testes.
    with patch("src.web.app.start_scheduler"), patch("src.web.app.shutdown_scheduler"):
        with TestClient(app) as test_client:
            yield test_client


class TestWebPages:
    """Páginas HTML devem responder 200."""

    @pytest.mark.parametrize("path", ["/", "/analytics", "/reminders", "/settings", "/report"])
    def test_pages_render(self, client, path):
        assert client.get(path).status_code == 200


class TestWebApi:
    """Endpoints de API principais."""

    def test_list_tickets_empty(self, client):
        assert client.get("/api/tickets").json() == {"tickets": []}

    def test_analytics(self, client):
        data = client.get("/api/analytics").json()
        assert data["total"] == 0
        assert "by_category" in data

    def test_reminder_crud(self, client):
        created = client.post(
            "/api/reminders",
            json={"title": "Ligar", "note": "", "remind_at": "2026-07-01T09:00"},
        )
        assert created.status_code == 200
        reminder_id = created.json()["id"]

        listed = client.get("/api/reminders").json()["reminders"]
        assert len(listed) == 1

        assert client.post(f"/api/reminders/{reminder_id}/done").status_code == 200
        assert client.delete(f"/api/reminders/{reminder_id}").status_code == 200

    def test_settings_save_masks_secret(self, client):
        resp = client.post("/api/settings", json={"company_name": "Floatech"})
        assert resp.status_code == 200
        assert "AI_API_KEY" not in resp.json()["settings"]

    def test_ticket_not_found(self, client):
        assert client.get("/api/tickets/999").status_code == 404

    def test_report_exports(self, client):
        assert client.get("/api/report.csv").status_code == 200
        assert client.get("/api/report.json").status_code == 200
