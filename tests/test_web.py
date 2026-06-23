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

    @pytest.mark.parametrize("path", ["/", "/analytics", "/clientes", "/reminders", "/anexos", "/settings", "/report"])
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


class TestHealth:
    """Endpoint de health-check (sem autenticação)."""

    def test_healthz_ok(self, anon_client):
        resp = anon_client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"]


class TestTicketActions:
    """Mudança de status, exclusão e isolamento das ações por cliente."""

    def test_status_update_and_delete(self, client):
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        ticket_id = db.save_ticket(
            {"user_id": user.id, "uid": "10", "sender": "x@x.com", "subject": "Teste"}
        )

        resp = client.post(f"/api/tickets/{ticket_id}/status", json={"status": "Resolvido"})
        assert resp.status_code == 200
        assert client.get(f"/api/tickets/{ticket_id}").json()["status"] == "Resolvido"

        assert client.delete(f"/api/tickets/{ticket_id}").status_code == 200
        assert client.get(f"/api/tickets/{ticket_id}").status_code == 404

    def test_status_filter(self, client):
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        tid = db.save_ticket({"user_id": user.id, "uid": "11", "sender": "x@x.com", "subject": "P"})
        client.post(f"/api/tickets/{tid}/status", json={"status": "Resolvido"})

        resolved = client.get("/api/tickets?status=Resolvido").json()["tickets"]
        assert [t["id"] for t in resolved] == [tid]
        assert client.get("/api/tickets?status=Pendente").json()["tickets"] == []

    def test_cannot_touch_other_tenant_ticket(self, client):
        """Cliente A não pode alterar nem excluir ticket do cliente B (404)."""
        from src.data import db

        uid_b = db.create_user("Cliente B", "b2@test.com", "x")
        tid_b = db.save_ticket({"user_id": uid_b, "uid": "99", "sender": "y@y.com", "subject": "B"})

        assert client.post(f"/api/tickets/{tid_b}/status", json={"status": "Resolvido"}).status_code == 404
        assert client.delete(f"/api/tickets/{tid_b}").status_code == 404

    def test_ordering_urgent_first_resolved_last(self, client):
        """Abertos no topo (urgência primeiro); resolvidos afundam para o fim."""
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        db.save_ticket({"user_id": user.id, "uid": "20", "sender": "x@x.com",
                        "subject": "baixa-aberta", "urgencia": "Baixa", "status": "Pendente"})
        db.save_ticket({"user_id": user.id, "uid": "21", "sender": "x@x.com",
                        "subject": "alta-aberta", "urgencia": "Alta", "status": "Pendente"})
        db.save_ticket({"user_id": user.id, "uid": "22", "sender": "x@x.com",
                        "subject": "alta-resolvida", "urgencia": "Alta", "status": "Resolvido"})

        subjects = [t["subject"] for t in client.get("/api/tickets").json()["tickets"]]
        assert subjects == ["alta-aberta", "baixa-aberta", "alta-resolvida"]

    def test_ticket_dict_has_utc_marker_and_html(self, client):
        """created_at sai com 'Z' (UTC) p/ o navegador localizar; body_html é exposto."""
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        tid = db.save_ticket({
            "user_id": user.id, "uid": "60", "sender": "x@x.com",
            "subject": "HTML", "body": "oi", "body_html": "<b>oi</b>",
        })
        t = client.get(f"/api/tickets/{tid}").json()
        assert t["created_at"].endswith("Z")
        assert t["body_html"] == "<b>oi</b>"

    def test_reanalyze_updates_classification(self, client):
        """Reanalisar reprocessa o ticket com a IA e atualiza a classificação."""
        from unittest.mock import patch

        from src.data import db

        user = db.get_user_by_email("a@test.com")
        tid = db.save_ticket({
            "user_id": user.id, "uid": "70", "sender": "promo@loja.com",
            "subject": "Cupom!", "body": "Aproveite descontos!", "urgencia": "Alta",
            "categoria": "Financeiro",
        })
        with patch("src.web.routes.api.AIService") as MockAI:
            MockAI.return_value.analyze_ticket.return_value = {
                "urgencia": "Baixa", "categoria": "Outros",
                "resumo": "E-mail promocional", "resposta_sugerida": "Obrigado!",
            }
            resp = client.post(f"/api/tickets/{tid}/reanalyze")
        assert resp.status_code == 200
        t = client.get(f"/api/tickets/{tid}").json()
        assert t["urgencia"] == "Baixa"
        assert t["categoria"] == "Outros"


class TestEmailConnection:
    """O teste de conexão de e-mail deve devolver um motivo claro."""

    def test_test_email_without_config_returns_clear_error(self, client):
        resp = client.post("/api/settings/test-email", json={})
        assert resp.status_code == 400
        assert "senha" in resp.json()["detail"].lower()

    def test_test_email_uses_form_credentials(self, client):
        """As credenciais digitadas no formulário são usadas no teste (não só as salvas)."""
        from unittest.mock import patch

        with patch("src.web.routes.api.EmailService") as MockSvc:
            MockSvc.return_value.test_connection.return_value = None
            resp = client.post(
                "/api/settings/test-email",
                json={"email_user": "x@gmail.com", "email_pass": "app-pass-123"},
            )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestSendersAndAttachments:
    """Clientes (remetentes), filtro por remetente e guia de anexos."""

    def test_senders_listed_with_counts(self, client):
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        db.save_ticket({"user_id": user.id, "uid": "30", "sender": "apple@x.com", "subject": "A1", "status": "Pendente"})
        db.save_ticket({"user_id": user.id, "uid": "31", "sender": "apple@x.com", "subject": "A2", "status": "Resolvido"})
        db.save_ticket({"user_id": user.id, "uid": "32", "sender": "linkedin@x.com", "subject": "L1", "status": "Pendente"})

        senders = {s["sender"]: s for s in client.get("/api/senders").json()["senders"]}
        assert senders["apple@x.com"]["total"] == 2
        assert senders["apple@x.com"]["abertos"] == 1  # 1 aberto, 1 resolvido
        assert senders["linkedin@x.com"]["total"] == 1

    def test_sender_filter(self, client):
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        db.save_ticket({"user_id": user.id, "uid": "40", "sender": "apple@x.com", "subject": "AA"})
        db.save_ticket({"user_id": user.id, "uid": "41", "sender": "linkedin@x.com", "subject": "LL"})

        tickets = client.get("/api/tickets?sender=apple@x.com").json()["tickets"]
        assert [t["subject"] for t in tickets] == ["AA"]

    def test_attachments_list(self, client):
        from src.data import db

        user = db.get_user_by_email("a@test.com")
        tid = db.save_ticket({"user_id": user.id, "uid": "50", "sender": "apple@x.com", "subject": "Com anexo"})
        db.add_attachment({"ticket_id": tid, "filename": "contrato.pdf", "content_type": "application/pdf", "size": 2048})

        atts = client.get("/api/attachments").json()["attachments"]
        assert len(atts) == 1
        assert atts[0]["filename"] == "contrato.pdf"
        assert atts[0]["ticket_subject"] == "Com anexo"
        assert atts[0]["ticket_sender"] == "apple@x.com"


class TestBrandingAndPreview:
    """Configuração de classificação/marca e pré-visualização do e-mail."""

    def test_save_branding_settings(self, client):
        resp = client.post("/api/settings", json={
            "categories": "Suporte,Vendas",
            "company_name": "Doce & Festa",
            "company_phone": "(77) 99999-0000",
            "email_template": "classico",
        })
        assert resp.status_code == 200
        s = resp.json()["settings"]
        assert s["CATEGORIES"] == "Suporte,Vendas"
        assert s["COMPANY_PHONE"] == "(77) 99999-0000"
        assert s["EMAIL_TEMPLATE"] == "classico"

    def test_email_preview_html_has_footer(self, client):
        resp = client.post("/api/email/preview", json={
            "email_template": "moderno",
            "company_name": "Doce & Festa",
            "company_phone": "(77) 99999-0000",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"
        assert "Doce &amp; Festa" in data["html"]
        assert "(77) 99999-0000" in data["html"]

    def test_email_preview_plain(self, client):
        resp = client.post("/api/email/preview", json={"email_format": "plain"})
        assert resp.json()["format"] == "plain"
        assert resp.json()["text"]

    def test_email_preview_uses_accent_color(self, client):
        resp = client.post("/api/email/preview", json={
            "email_template": "moderno", "email_accent": "#FF6600",
        })
        assert "#FF6600" in resp.json()["html"]

    def test_logo_upload_and_serve(self, client):
        from src.data import db

        png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        up = client.post("/api/logo", files={"file": ("logo.png", png, "image/png")})
        assert up.status_code == 200
        assert "/logo/" in up.json()["url"]

        uid = db.get_user_by_email("a@test.com").id
        served = client.get(f"/logo/{uid}")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("image/")

    def test_logo_upload_rejects_non_image(self, client):
        resp = client.post("/api/logo", files={"file": ("x.txt", b"hello", "text/plain")})
        assert resp.status_code == 400
