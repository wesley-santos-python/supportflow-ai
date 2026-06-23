"""
Roteador de API (JSON) do SupportFlow AI.

Todas as rotas exigem autenticação e operam apenas sobre os dados do cliente
logado. Agrupa as ações do SaaS: sincronização, listagem/filtros de tickets,
envio e agendamento de respostas, reescrita por IA, lembretes, anexos,
configurações por cliente, analytics e exportação de relatórios.
"""
import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from src.core import attachments as attachment_manager
from src.core import reports
from src.core.ai_engine import AIService
from src.core.automation import SupportController
from src.core.email_service import EmailService
from src.data import db
from src.data.models import ScheduledReply, User
from src.exceptions import EmailConnectionError
from src.user_config import UserConfig
from src.utils.logger import get_logger
from src.web.auth import require_api_user

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
    """Configurações do cliente (e-mail e WhatsApp). Campos opcionais."""

    email_user: Optional[str] = None
    email_pass: Optional[str] = None
    email_provider: Optional[str] = None
    imap_server: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[str] = None
    auto_download_attachments: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_to: Optional[str] = None
    whatsapp_token: Optional[str] = None


# ---------------------------------------------------------------------------
# Sincronização e tickets
# ---------------------------------------------------------------------------
@router.post("/sync")
def sync_now(user: User = Depends(require_api_user)):
    """Dispara uma sincronização manual de e-mails do cliente."""
    try:
        processed = SupportController(user.id).run_sync()
    except EmailConnectionError as e:
        # Mostra o motivo real (ex.: senha de app incorreta) em vez de "0 tickets".
        raise HTTPException(status_code=400, detail=e.message)
    return {"processed": processed}


@router.get("/tickets")
def list_tickets(
    categoria: Optional[str] = None,
    urgencia: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_api_user),
):
    """Lista os tickets do cliente aplicando filtros opcionais."""
    tickets = db.query_tickets(user.id, categoria, urgencia, status, search)
    return {"tickets": [t.to_dict() for t in tickets]}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, user: User = Depends(require_api_user)):
    """Retorna os detalhes de um ticket do cliente, incluindo anexos."""
    ticket = db.get_ticket_by_id(ticket_id, user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return ticket.to_dict(include_attachments=True)


@router.post("/tickets/{ticket_id}/status")
def set_status(ticket_id: int, payload: StatusUpdate, user: User = Depends(require_api_user)):
    """Atualiza o status de um ticket do cliente."""
    if not db.update_ticket_status(ticket_id, payload.status, user.id):
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return {"ok": True}


@router.delete("/tickets/{ticket_id}")
def remove_ticket(ticket_id: int, user: User = Depends(require_api_user)):
    """Remove um ticket do cliente."""
    if not db.delete_ticket(ticket_id, user.id):
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return {"ok": True}


@router.post("/tickets/{ticket_id}/rewrite")
def rewrite(ticket_id: int, payload: RewriteRequest, user: User = Depends(require_api_user)):
    """Reescreve uma resposta usando a IA conforme a instrução fornecida."""
    if not db.get_ticket_by_id(ticket_id, user.id):
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    new_text = AIService().rewrite_response(payload.text, payload.instruction)
    db.update_ticket_suggestion(ticket_id, new_text, user.id)
    return {"text": new_text}


@router.post("/tickets/{ticket_id}/reply")
async def reply(
    ticket_id: int,
    body: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    user: User = Depends(require_api_user),
):
    """Envia uma resposta ao ticket agora, com anexos opcionais (multipart)."""
    paths = await _save_uploads(files)
    ok = SupportController(user.id).send_ticket_reply(ticket_id, body, paths)
    if not ok:
        raise HTTPException(status_code=400, detail="Falha ao enviar resposta")
    return {"ok": True}


@router.post("/tickets/{ticket_id}/schedule")
async def schedule_reply(
    ticket_id: int,
    body: str = Form(...),
    scheduled_for: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    user: User = Depends(require_api_user),
):
    """Agenda uma resposta para envio futuro (com anexos opcionais)."""
    ticket = db.get_ticket_by_id(ticket_id, user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")

    paths = await _save_uploads(files)
    reply_id = db.create_scheduled_reply(
        {
            "user_id": user.id,
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
def download_attachment(attachment_id: int, user: User = Depends(require_api_user)):
    """Baixa o anexo do servidor de e-mail e o salva de forma organizada."""
    _require_attachment_owner(attachment_id, user.id)
    path = attachment_manager.download_attachment(attachment_id, UserConfig(user.id))
    if not path:
        raise HTTPException(status_code=400, detail="Não foi possível baixar o anexo")
    return {"ok": True, "path": path}


@router.get("/attachments/{attachment_id}/file")
def serve_attachment(attachment_id: int, user: User = Depends(require_api_user)):
    """Serve o arquivo do anexo (para visualizar/imprimir), baixando se preciso."""
    attachment = _require_attachment_owner(attachment_id, user.id)
    path = attachment.stored_path
    if not path or not os.path.isfile(path):
        path = attachment_manager.download_attachment(attachment_id, UserConfig(user.id))
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Arquivo indisponível")
    return FileResponse(path, filename=attachment.filename)


# ---------------------------------------------------------------------------
# Lembretes
# ---------------------------------------------------------------------------
@router.get("/reminders")
def list_reminders(user: User = Depends(require_api_user)):
    """Lista os lembretes do cliente."""
    return {"reminders": [r.to_dict() for r in db.list_reminders(user.id)]}


@router.post("/reminders")
def create_reminder(payload: ReminderRequest, user: User = Depends(require_api_user)):
    """Cria um novo lembrete para o cliente."""
    reminder_id = db.create_reminder(
        {
            "user_id": user.id,
            "title": payload.title,
            "note": payload.note,
            "remind_at": _parse_datetime(payload.remind_at),
            "ticket_id": payload.ticket_id,
        }
    )
    return {"ok": True, "id": reminder_id}


@router.post("/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: int, user: User = Depends(require_api_user)):
    """Marca um lembrete do cliente como concluído."""
    if not db.set_reminder_done(reminder_id, True, user.id):
        raise HTTPException(status_code=404, detail="Lembrete não encontrado")
    return {"ok": True}


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, user: User = Depends(require_api_user)):
    """Remove um lembrete do cliente."""
    if not db.delete_reminder(reminder_id, user.id):
        raise HTTPException(status_code=404, detail="Lembrete não encontrado")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Analytics, configurações e relatórios
# ---------------------------------------------------------------------------
@router.get("/analytics")
def analytics(user: User = Depends(require_api_user)):
    """Retorna as métricas agregadas do cliente para os gráficos."""
    return db.analytics_summary(user.id)


@router.post("/settings")
def save_settings(payload: SettingsRequest, user: User = Depends(require_api_user)):
    """Salva as configurações de e-mail/WhatsApp do cliente (segredos criptografados)."""
    cfg = UserConfig(user.id)

    if payload.email_provider:
        cfg.apply_email_provider(payload.email_provider)

    mapping = {
        "EMAIL_USER": payload.email_user,
        "EMAIL_PASS": payload.email_pass,
        "IMAP_SERVER": payload.imap_server,
        "SMTP_SERVER": payload.smtp_server,
        "SMTP_PORT": payload.smtp_port,
        "WHATSAPP_TO": payload.whatsapp_to,
        "WHATSAPP_TOKEN": payload.whatsapp_token,
    }
    # Não sobrescreve segredos com string vazia (mantém o valor existente).
    for key, value in mapping.items():
        if value not in (None, ""):
            cfg.set(key, value)

    if payload.auto_download_attachments is not None:
        cfg.set("AUTO_DOWNLOAD_ATTACHMENTS", str(payload.auto_download_attachments).lower())
    if payload.whatsapp_enabled is not None:
        cfg.set("WHATSAPP_ENABLED", str(payload.whatsapp_enabled).lower())

    return {"ok": True, "settings": cfg.public_settings()}


@router.post("/settings/test-email")
def test_email(user: User = Depends(require_api_user)):
    """Testa a conexão IMAP com as credenciais salvas e devolve o motivo de falha."""
    try:
        EmailService(UserConfig(user.id)).test_connection()
    except EmailConnectionError as e:
        raise HTTPException(status_code=400, detail=e.message)
    return {"ok": True, "message": "Conexão bem-sucedida! Seu e-mail está pronto."}


@router.get("/report.json")
def report_json(user: User = Depends(require_api_user)):
    """Exporta os tickets do cliente em JSON (download)."""
    data = [t.to_dict(include_attachments=True) for t in db.get_all_tickets(user.id)]
    headers = {"Content-Disposition": "attachment; filename=relatorio.json"}
    return JSONResponse(content=data, headers=headers)


@router.get("/report.csv")
def report_csv(user: User = Depends(require_api_user)):
    """Exporta os tickets do cliente em CSV (download)."""
    content = reports.csv_string(db.get_all_tickets(user.id))
    headers = {"Content-Disposition": "attachment; filename=relatorio.csv"}
    return Response(content=content, media_type="text/csv", headers=headers)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_attachment_owner(attachment_id: int, user_id: int):
    """Retorna o anexo garantindo que pertence ao cliente, ou 404."""
    attachment = db.get_attachment(attachment_id)
    if not attachment or not db.get_ticket_by_id(attachment.ticket_id, user_id):
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    return attachment


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
