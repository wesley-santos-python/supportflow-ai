"""
Roteador de páginas HTML (renderização server-side com Jinja2).

Todas as páginas exigem autenticação; visitantes são redirecionados ao login.
Os dados são sempre escopados ao cliente logado.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.data import db
from src.user_config import UserConfig
from src.web import auth

router = APIRouter()


def _templates():
    """Acesso tardio aos templates (evita import circular com app)."""
    from src.web.app import templates

    return templates


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Painel principal com cards de tickets e filtros."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    cfg = UserConfig(user.id)
    return _templates().TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user.to_dict(),
            "active": "dashboard",
            "summary": db.analytics_summary(user.id),
            "email_ok": cfg.is_email_configured(),
        },
    )


@router.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    """Painel de análise com gráficos."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _templates().TemplateResponse(
        request,
        "analytics.html",
        {"user": user.to_dict(), "active": "analytics", "summary": db.analytics_summary(user.id)},
    )


@router.get("/clientes", response_class=HTMLResponse)
def clientes(request: Request):
    """Lista os clientes (remetentes), com alerta para e-mails suspeitos."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _templates().TemplateResponse(
        request,
        "clientes.html",
        {"user": user.to_dict(), "active": "clientes", "clientes": db.list_senders(user.id)},
    )


@router.get("/reminders", response_class=HTMLResponse)
def reminders(request: Request):
    """Página de lembretes e respostas agendadas."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _templates().TemplateResponse(
        request,
        "reminders.html",
        {
            "user": user.to_dict(),
            "active": "reminders",
            "reminders": db.list_reminders(user.id),
            "scheduled": db.list_scheduled_replies(user.id),
        },
    )


@router.get("/anexos", response_class=HTMLResponse)
def anexos(request: Request):
    """Guia de anexos: arquivos reais agrupados por cliente (remetente)."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    from src.core import attachments as attachment_manager
    from src.core.sender_risk import extract_email

    grupos: dict = {}
    for att in db.list_attachments(user.id):
        if not attachment_manager.is_real_file(att.get("filename"), att.get("content_type")):
            continue
        sender = att.get("ticket_sender") or "(desconhecido)"
        grupo = grupos.setdefault(
            sender,
            {"sender": sender, "email": extract_email(sender) or sender, "files": []},
        )
        grupo["files"].append(att)

    clientes = sorted(grupos.values(), key=lambda g: len(g["files"]), reverse=True)
    return _templates().TemplateResponse(
        request,
        "attachments.html",
        {"user": user.to_dict(), "active": "anexos", "clientes": clientes},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    """Página de configurações do cliente (conexão de e-mail, WhatsApp...)."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    from src import config

    return _templates().TemplateResponse(
        request,
        "settings.html",
        {
            "user": user.to_dict(),
            "active": "settings",
            "settings": UserConfig(user.id).public_settings(),
            "providers": list(config.EMAIL_PROVIDERS.keys()),
        },
    )


@router.get("/report", response_class=HTMLResponse)
def report(request: Request):
    """Relatório imprimível (o navegador permite salvar/imprimir em PDF)."""
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    from src.core import reports

    context = reports.report_context(user.id)
    context["user"] = user.to_dict()
    context["active"] = "report"
    return _templates().TemplateResponse(request, "report.html", context)
