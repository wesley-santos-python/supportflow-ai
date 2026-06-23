"""
Testes de integração da camada web (FastAPI) com autenticação multi-cliente.

Usa um banco em memória compartilhado e não inicia o agendador real.
"""
import pytest


def _make_client():
    """Cria um TestClient com banco em memória e scheduler desligado."""
    from unittest.mock import patch

    import src.data.db as db_module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from src.data.models import Base

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

    for p in (patch("src.web.app.start_scheduler"), patch("src.web.app.shutdown_scheduler")):
        p.start()
    return TestClient(app)


@pytest.fixture
def anon_client():
    """Cliente HTTP sem autenticação."""
    with _make_client() as client:
        yield client


@pytest.fixture
def client():
    """Cliente HTTP já autenticado (registra e loga um usuário)."""
    with _make_client() as c:
        resp = c.post(
            "/register",
            data={"name": "Cliente A", "email": "a@test.com", "password": "secret123"},
        )
        assert resp.status_code == 200  # redirecionado para "/"
        yield c


class TestAuthFlow:
    """Cadastro, login e proteção de rotas."""

    def test_protected_redirects_when_anonymous(self, anon_client):
        resp = anon_client.get("/", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

    def test_api_requires_auth(self, anon_client):
        assert anon_client.get("/api/tickets").status_code == 401

    def test_login_page_renders(self, anon_client):
        assert anon_client.get("/login").status_code == 200

    def test_register_and_logout(self, anon_client):
        resp = anon_client.post(
            "/register",
            data={"name": "Novo", "email": "novo@test.com", "password": "abcdef"},
        )
        assert resp.status_code == 200
        assert anon_client.get("/api/tickets").status_code == 200
        anon_client.get("/logout")
        assert anon_client.get("/api/tickets").status_code == 401

    def test_duplicate_email_rejected(self, anon_client):
        anon_client.post("/register", data={"name": "A", "email": "dup@test.com", "password": "abcdef"})
        anon_client.get("/logout")
        resp = anon_client.post(
            "/register",
            data={"name": "B", "email": "dup@test.com", "password": "abcdef"},
        )
        assert "já está cadastrado" in resp.text


class TestWebPages:
    """Páginas HTML autenticadas devem responder 200."""

    @pytest.mark.parametrize("path", ["/", "/analytics", "/reminders", "/settings", "/report"])
    def test_pages_render(self, client, path):
        assert client.get(path).status_code == 200


class TestWebApi:
    """Endpoints de API autenticados."""

    def test_list_tickets_empty(self, client):
        assert client.get("/api/tickets").json() == {"tickets": []}

    def test_analytics(self, client):
        assert client.get("/api/analytics").json()["total"] == 0

    def test_reminder_crud(self, client):
        created = client.post(
            "/api/reminders",
            json={"title": "Ligar", "note": "", "remind_at": "2026-07-01T09:00"},
        )
        assert created.status_code == 200
        reminder_id = created.json()["id"]
        assert len(client.get("/api/reminders").json()["reminders"]) == 1
        assert client.post(f"/api/reminders/{reminder_id}/done").status_code == 200
        assert client.delete(f"/api/reminders/{reminder_id}").status_code == 200

    def test_settings_save_masks_secret(self, client):
        resp = client.post("/api/settings", json={"email_user": "x@gmail.com"})
        assert resp.status_code == 200
        settings = resp.json()["settings"]
        assert "EMAIL_PASS" not in settings  # somente o indicador *_set
        assert settings["EMAIL_USER"] == "x@gmail.com"

    def test_ticket_not_found(self, client):
        assert client.get("/api/tickets/999").status_code == 404

    def test_report_exports(self, client):
        assert client.get("/api/report.csv").status_code == 200
        assert client.get("/api/report.json").status_code == 200


class TestTenantIsolation:
    """Cada cliente enxerga apenas os próprios dados."""

    def test_users_only_see_their_tickets(self, client):
        from src.data import db

        user_a = db.get_user_by_email("a@test.com")
        uid_b = db.create_user("Cliente B", "b@test.com", "x")
        db.save_ticket({"user_id": user_a.id, "uid": "1", "sender": "x@x.com", "subject": "A"})
        db.save_ticket({"user_id": uid_b, "uid": "1", "sender": "y@y.com", "subject": "B"})

        tickets = client.get("/api/tickets").json()["tickets"]
        assert len(tickets) == 1
        assert tickets[0]["subject"] == "A"
