"""
Controlador de automação do SupportFlow AI.

Orquestra o fluxo principal de um cliente: e-mail -> IA -> banco de dados,
registrando também os metadados de anexos. Centraliza o envio de respostas
(manuais, sugeridas pela IA ou agendadas).

Cada instância opera no contexto de um cliente (``user_id``), usando a conexão
de e-mail daquele cliente. A IA (Gemini) é global, fornecida pelo provedor do
SaaS via variáveis de ambiente.
"""
import json
import re
from datetime import datetime
from typing import List, Optional

from src.core.ai_engine import AIService
from src.core.email_service import EmailService
from src.data import db
from src.exceptions import EmailSendError
from src.user_config import UserConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _html_to_text(html: str) -> str:
    """Extrai texto legível de um HTML (para analisar e-mails só-HTML)."""
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class SupportController:
    """
    Controlador que orquestra o fluxo de suporte de um cliente.

    Args:
        user_id: Cliente dono da operação. Usa a conexão de e-mail e as
                 preferências desse cliente.
    """

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.cfg = UserConfig(user_id)
        self.email_api = EmailService(self.cfg)
        self.ai_api = AIService()
        logger.info(f"SupportController inicializado (user={user_id})")

    def run_sync(self) -> int:
        """
        Sincroniza os e-mails do cliente: busca, analisa com IA e salva.

        Returns:
            Número de tickets processados.
        """
        logger.info(f"Sincronizando e-mails (user={self.user_id})...")

        # Sincroniza sempre apenas os não lidos dos ÚLTIMOS 7 DIAS (não varre
        # backlog antigo). Como os processados são marcados como lidos, na
        # prática só os e-mails novos entram a cada ciclo.
        # Propaga EmailConnectionError para a UI mostrar o motivo real
        # (senha de app incorreta, servidor errado, etc.) em vez de "0 tickets".
        new_emails = self.email_api.fetch_unread_emails(since_days=7)
        if not new_emails:
            return 0

        auto_download = self.cfg.get_bool("AUTO_DOWNLOAD_ATTACHMENTS", False)
        processed = 0

        for mail in new_emails:
            # Um e-mail problemático não deve derrubar o lote inteiro.
            try:
                html = mail.get("html") or ""
                text = (mail.get("body") or "").strip()
                # Conteúdo para a IA: usa o texto; se for e-mail só-HTML, extrai do HTML.
                content = text or _html_to_text(html)
                if not content:
                    logger.warning(f"E-mail sem conteúdo ignorado: {mail.get('subject')}")
                    self.email_api.mark_as_read(mail["id"])
                    continue

                logger.info(f"Analisando ticket: {mail['subject']}")
                analysis = self.ai_api.analyze_ticket(
                    content,
                    categories=self.cfg.get("CATEGORIES"),
                    urgency_criteria=self.cfg.get("URGENCY_CRITERIA"),
                )

                ticket_data = {
                    "user_id": self.user_id,
                    "uid": mail["id"],
                    "sender": mail["sender"],
                    "subject": mail["subject"],
                    "body": text or content,
                    "body_html": html or None,
                    "urgencia": analysis.get("urgencia", "Média"),
                    "categoria": analysis.get("categoria", "Outros"),
                    "resumo": analysis.get("resumo", "Sem resumo"),
                    "resposta_sugerida": analysis.get("resposta_sugerida", ""),
                }

                ticket_id = db.save_ticket(ticket_data)
                if not ticket_id:
                    # Duplicado (já existe): marca como lido para NÃO reprocessar
                    # o mesmo e-mail a cada ciclo (evita loop e gasto de IA).
                    self.email_api.mark_as_read(mail["id"])
                    continue

                self._register_attachments(ticket_id, mail.get("attachments", []), auto_download)
                self.email_api.mark_as_read(mail["id"])
                processed += 1
            except Exception as e:
                logger.error(f"Falha ao processar e-mail '{mail.get('subject')}': {e}")
                continue

        logger.info(f"Sincronização concluída (user={self.user_id}): {processed} tickets")
        return processed

    def send_ticket_reply(
        self,
        ticket_id: int,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """Envia uma resposta a um ticket do cliente e o marca como resolvido."""
        ticket = db.get_ticket_by_id(ticket_id, self.user_id)
        if not ticket:
            logger.warning(f"Ticket {ticket_id} não encontrado para resposta")
            return False

        subject = f"Re: {ticket.subject}" if ticket.subject else "Re: Suporte"
        # Deixa EmailSendError propagar para a UI mostrar o motivo real
        # (ex.: senha de app incorreta) em vez de uma falha genérica.
        self.email_api.send_reply(ticket.sender, subject, body, attachments)
        db.mark_ticket_responded(ticket_id, self.user_id)
        return True

    def process_scheduled_replies(self) -> int:
        """
        Envia as respostas agendadas DESTE cliente cujo horário já chegou.

        Returns:
            Número de respostas enviadas com sucesso.
        """
        due = db.due_scheduled_replies(datetime.now(), user_id=self.user_id)
        sent = 0
        for reply in due:
            attachments = json.loads(reply.attachments_json) if reply.attachments_json else []
            try:
                self.email_api.send_reply(
                    reply.to_email, reply.subject, reply.body, attachments
                )
                db.update_scheduled_reply_status(reply.id, reply.STATUS_SENT)
                db.mark_ticket_responded(reply.ticket_id, self.user_id)
                sent += 1
                logger.info(f"Resposta agendada #{reply.id} enviada")
            except EmailSendError as e:
                db.update_scheduled_reply_status(reply.id, reply.STATUS_FAILED, e.message)
                logger.error(f"Falha na resposta agendada #{reply.id}: {e.message}")
        return sent

    def _register_attachments(
        self, ticket_id: int, attachments: List[dict], auto_download: bool
    ) -> None:
        """Registra metadados de anexos e, se configurado, baixa-os."""
        # Import tardio: evita ciclo (attachments -> email_service).
        from src.core import attachments as attachment_manager

        for meta in attachments or []:
            attachment_id = db.add_attachment(
                {
                    "ticket_id": ticket_id,
                    "filename": meta.get("filename", "arquivo"),
                    "content_type": meta.get("content_type"),
                    "size": meta.get("size", 0),
                }
            )
            # Só baixa arquivos de verdade (PDF, imagens nomeadas...). Evita
            # baixar imagens de rastreio/inline de newsletters, que travam o sync.
            if (
                auto_download
                and attachment_id
                and attachment_manager.is_real_file(meta.get("filename"), meta.get("content_type"))
            ):
                attachment_manager.download_attachment(attachment_id, self.cfg)
