"""
Testes para a camada web (FastAPI + HTMX + API JSON).
"""
import pytest
from fastapi.testclient import TestClient

import src.data.db as db_module
from src.data.db import create_ticket
from src.web.app import app


@pytest.fixture
def client():
    """TestClient com o banco SQLite em memória inicializado."""
    db_module.init_db()
    with db_module.SessionLocal() as s:
        s.query(db_module.Ticket).delete()
        s.commit()
    with TestClient(app) as c:
        yield c


def _seed(**extra):
    with db_module.SessionLocal() as s:
        data = {
            "uid": extra.get("uid", "web-1"),
            "sender": "cliente@x.com",
            "subject": "Assunto de teste",
            "body": "corpo",
            "urgencia": "Alta",
            "categoria": "Técnico",
            "resumo": "Resumo de teste",
            "resposta_sugerida": "Resposta",
        }
        data.update(extra)
        return create_ticket(s, data)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_index_renders(client):
    _seed()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SupportFlow AI" in resp.text
    assert "Assunto de teste" in resp.text


def test_api_tickets_and_stats(client):
    _seed(uid="api-1")
    tickets = client.get("/api/tickets").json()
    assert len(tickets) >= 1
    assert tickets[0]["categoria"] == "Técnico"

    stats = client.get("/api/stats").json()
    assert stats["total"] >= 1
    assert stats["alta"] >= 1


def test_tickets_fragment_filter(client):
    _seed(uid="f1", categoria="Técnico", subject="Login falhou")
    _seed(uid="f2", categoria="Financeiro", subject="Cobrança")

    resp = client.get("/tickets", params={"categoria": "Financeiro"})
    assert resp.status_code == 200
    assert "Cobrança" in resp.text
    assert "Login falhou" not in resp.text


def test_update_status(client):
    ticket = _seed(uid="st-1")
    resp = client.post(f"/tickets/{ticket.id}/status", data={"status": "Resolvido"})
    assert resp.status_code == 200
    assert "Resolvido" in resp.text
    # KPIs devem ser atualizados via HX-Trigger
    assert "refreshKpis" in resp.headers.get("HX-Trigger", "")


def test_update_status_invalid(client):
    ticket = _seed(uid="st-2")
    resp = client.post(f"/tickets/{ticket.id}/status", data={"status": "Inexistente"})
    assert resp.status_code == 400


def test_delete_ticket(client):
    ticket = _seed(uid="del-1")
    resp = client.request("DELETE", f"/tickets/{ticket.id}")
    assert resp.status_code == 200
    assert client.get(f"/tickets/{ticket.id}/detail").status_code == 404


def test_sync_without_config_warns(client):
    """Sem credenciais, /sync devolve a lista e um toast de erro."""
    resp = client.post("/sync")
    assert resp.status_code == 200
    assert "toast" in resp.headers.get("HX-Trigger", "")
