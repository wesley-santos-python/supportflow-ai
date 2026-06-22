"""
Roteador de API (JSON) do SupportFlow AI.

Agrupa as ações do SaaS: sincronização, listagem/ filtros de tickets, envio e
agendamento de respostas, reescrita por IA, lembretes, anexos, configurações,
analytics e exportação de relatórios.
"""
import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from src import config
from src.core import attachments as attachment_manager
from src.core import reports
from src.core.ai_engine import AIService
from src.core.automation import SupportController
from src.data import db
from src.data.models import ScheduledReply
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

_UPLOADS_DIR = "data/uploads"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class StatusUpdate(BaseModel):
    """Payload para atualização de status do ticket."""

    status: str


class RewriteRequest(BaseModel):
    """Payload para reescrita de resposta pela IA."""

    text: str
    instruction: str


class ReminderRequest(BaseModel):
    """Payload para criação de lembrete."""

    title: str
    note: Optional[str] = ""
    remind_at: str
    ticket_id: Optional[int] = None


class SettingsRequest(BaseModel):
    """Payload de configurações (campos opcionais)."""

    company_name: Optional[str] = None
    email_user: Optional[str] = None
    email_pass: Optional[str] = None
    email_provider: Optional[str] = None
    imap_server: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[str] = None
    ai_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    sync_interval_minutes: Optional[str] = None
    auto_download_attachments: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_to: Optional[str] = None


# ---------------------------------------------------------------------------
# Sincronização e tickets
# ---------------------------------------------------------------------------
@router.post("/sync")
def sync_now():
    """Dispara uma sincronização manual de e-mails."""
    processed = SupportController().run_sync()
    return {"processed": processed}


@router.get("/tickets")
def list_tickets(
    categoria: Optional[str] = None,
    urgencia: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    """Lista tickets aplicando filtros opcionais."""
    tickets = db.query_tickets(categoria, urgencia, status, search)
    return {"tickets": [t.to_dict() for t in tickets]}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    """Retorna os detalhes de um ticket, incluindo anexos."""
    ticket = db.get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return ticket.to_dict(include_attachments=True)


@router.post("/tickets/{ticket_id}/status")
def set_status(ticket_id: int, payload: StatusUpdate):
    """Atualiza o status de um ticket."""
    if not db.update_ticket_status(ticket_id, payload.status):
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return {"ok": True}


@router.delete("/tickets/{ticket_id}")
def remove_ticket(ticket_id: int):
    """Remove um ticket."""
    if not db.delete_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return {"ok": True}


@router.post("/tickets/{ticket_id}/rewrite")
def rewrite(ticket_id: int, payload: RewriteRequest):
    """Reescreve uma resposta usando a IA conforme a instrução fornecida."""
    new_text = AIService().rewrite_response(payload.text, payload.instruction)
    db.update_ticket_suggestion(ticket_id, new_text)
    return {"text": new_text}


@router.post("/tickets/{ticket_id}/reply")
async def reply(
    ticket_id: int,
    body: str = Form(...),
    files: List[UploadFile] = File(default=[]),
):
    """
    Envia uma resposta ao ticket agora, com anexos opcionais.

    Aceita ``multipart/form-data`` para permitir o upload de arquivos.
    """
    paths = await _save_uploads(files)
    ok = SupportController().send_ticket_reply(ticket_id, body, paths)
    if not ok:
        raise HTTPException(status_code=400, detail="Falha ao enviar resposta")
    return {"ok": True}


@router.post("/tickets/{ticket_id}/schedule")
async def schedule_reply(
    ticket_id: int,
    body: str = Form(...),
    scheduled_for: str = Form(...),
    files: List[UploadFile] = File(default=[]),
):
    """Agenda uma resposta para envio futuro (com anexos opcionais)."""
    ticket = db.get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")

    paths = await _save_uploads(files)
    reply_id = db.create_scheduled_reply(
        {
            "ticket_id": ticket_id,
            "to_email": ticket.sender,
            "subject": f"Re: {ticket.subject}" if ticket.subject else "Re: Suporte",
            "body": body,
            "attachments_json": json.dumps(paths) if paths else None,
            "scheduled_for": _parse_datetime(scheduled_for),
            "status": ScheduledReply.STATUS_PENDING,
        }
    )
    return {"ok": True, "id": reply_id}


# ---------------------------------------------------------------------------
# Anexos
# ---------------------------------------------------------------------------
@router.post("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int):
    """Baixa o anexo do servidor de e-mail e o salva de forma organizada."""
    path = attachment_manager.download_attachment(attachment_id)
    if not path:
        raise HTTPException(status_code=400, detail="Não foi possível baixar o anexo")
    return {"ok": True, "path": path}


@router.get("/attachments/{attachment_id}/file")
def serve_attachment(attachment_id: int):
    """
    Serve o arquivo do anexo (para visualizar/imprimir pelo sistema).

    Baixa sob demanda caso ainda não esteja em disco.
    """
    attachment = db.get_attachment(attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    path = attachment.stored_path
    if not path or not os.path.isfile(path):
        path = attachment_manager.download_attachment(attachment_id)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Arquivo indisponível")
    return FileResponse(path, filename=attachment.filename)


# ---------------------------------------------------------------------------
# Lembretes
# ---------------------------------------------------------------------------
@router.get("/reminders")
def list_reminders():
    """Lista todos os lembretes."""
    return {"reminders": [r.to_dict() for r in db.list_reminders()]}


@router.post("/reminders")
def create_reminder(payload: ReminderRequest):
    """Cria um novo lembrete."""
    reminder_id = db.create_reminder(
        {
            "title": payload.title,
            "note": payload.note,
            "remind_at": _parse_datetime(payload.remind_at),
            "ticket_id": payload.ticket_id,
        }
    )
    return {"ok": True, "id": reminder_id}


@router.post("/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: int):
    """Marca um lembrete como concluído."""
    if not db.set_reminder_done(reminder_id, True):
        raise HTTPException(status_code=404, detail="Lembrete não encontrado")
    return {"ok": True}


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int):
    """Remove um lembrete."""
    if not db.delete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="Lembrete não encontrado")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Analytics, configurações e relatórios
# ---------------------------------------------------------------------------
@router.get("/analytics")
def analytics():
    """Retorna as métricas agregadas para os gráficos."""
    return db.analytics_summary()


@router.post("/settings")
def save_settings(payload: SettingsRequest):
    """
    Salva as configurações da aplicação.

    Aplica presets de provedor de e-mail quando informado e reinicia o
    agendador para refletir um novo intervalo de sincronização.
    """
    if payload.email_provider:
        config.apply_email_provider(payload.email_provider)

    mapping = {
        "COMPANY_NAME": payload.company_name,
        "EMAIL_USER": payload.email_user,
        "EMAIL_PASS": payload.email_pass,
        "IMAP_SERVER": payload.imap_server,
        "SMTP_SERVER": payload.smtp_server,
        "SMTP_PORT": payload.smtp_port,
        "AI_API_KEY": payload.ai_api_key,
        "GEMINI_MODEL": payload.gemini_model,
        "SYNC_INTERVAL_MINUTES": payload.sync_interval_minutes,
        "WHATSAPP_TO": payload.whatsapp_to,
    }
    # Não sobrescreve segredos com string vazia (mantém o valor existente).
    config.set_many({k: v for k, v in mapping.items() if v not in (None, "")})

    if payload.auto_download_attachments is not None:
        config.set_value("AUTO_DOWNLOAD_ATTACHMENTS", str(payload.auto_download_attachments).lower())
    if payload.whatsapp_enabled is not None:
        config.set_value("WHATSAPP_ENABLED", str(payload.whatsapp_enabled).lower())

    _restart_scheduler()
    return {"ok": True, "settings": config.public_settings()}


@router.get("/report.json")
def report_json():
    """Exporta todos os tickets em JSON (download)."""
    data = [t.to_dict(include_attachments=True) for t in db.get_all_tickets()]
    headers = {"Content-Disposition": "attachment; filename=relatorio.json"}
    return JSONResponse(content=data, headers=headers)


@router.get("/report.csv")
def report_csv():
    """Exporta todos os tickets em CSV (download)."""
    content = reports.csv_string(db.get_all_tickets())
    headers = {"Content-Disposition": "attachment; filename=relatorio.csv"}
    return Response(content=content, media_type="text/csv", headers=headers)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _save_uploads(files: List[UploadFile]) -> List[str]:
    """Salva uploads em ``data/uploads`` e retorna os caminhos gravados."""
    os.makedirs(_UPLOADS_DIR, exist_ok=True)
    paths: List[str] = []
    for upload in files or []:
        if not upload.filename:
            continue
        safe = attachment_manager.sanitize(upload.filename)
        dest = os.path.join(_UPLOADS_DIR, f"{int(datetime.now().timestamp())}_{safe}")
        with open(dest, "wb") as f:
            f.write(await upload.read())
        paths.append(dest)
    return paths


def _parse_datetime(value: str) -> datetime:
    """Converte uma string ISO/`datetime-local` em ``datetime``."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Data/hora inválida")


def _restart_scheduler() -> None:
    """Reinicia o agendador para aplicar novas configurações."""
    from src.core.scheduler import shutdown_scheduler, start_scheduler

    shutdown_scheduler()
    start_scheduler()
