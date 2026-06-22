"""
Roteador de páginas HTML (renderização server-side com Jinja2).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src import config
from src.data import db

router = APIRouter()


def _templates():
    """Acesso tardio aos templates (evita import circular com app)."""
    from src.web.app import templates

    return templates


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Painel principal com cards de tickets e filtros."""
    return _templates().TemplateResponse(
        request,
        "dashboard.html",
        {
            "active": "dashboard",
            "summary": db.analytics_summary(),
            "email_ok": config.is_email_configured(),
            "ai_ok": config.is_ai_configured(),
        },
    )


@router.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    """Painel de análise com gráficos."""
    return _templates().TemplateResponse(
        request,
        "analytics.html",
        {"active": "analytics", "summary": db.analytics_summary()},
    )


@router.get("/reminders", response_class=HTMLResponse)
def reminders(request: Request):
    """Página de lembretes e respostas agendadas."""
    return _templates().TemplateResponse(
        request,
        "reminders.html",
        {
            "active": "reminders",
            "reminders": db.list_reminders(),
            "scheduled": db.list_scheduled_replies(),
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    """Página de configurações (conexão de e-mail, IA, WhatsApp...)."""
    return _templates().TemplateResponse(
        request,
        "settings.html",
        {
            "active": "settings",
            "settings": config.public_settings(),
            "providers": list(config.EMAIL_PROVIDERS.keys()),
        },
    )


@router.get("/report", response_class=HTMLResponse)
def report(request: Request):
    """Relatório imprimível (o navegador permite salvar/imprimir em PDF)."""
    from src.core import reports

    context = reports.report_context()
    context["active"] = "report"
    return _templates().TemplateResponse(request, "report.html", context)
