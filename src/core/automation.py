"""
Controlador de automação do SupportFlow AI.

Orquestra o fluxo principal: e-mail -> IA -> banco de dados, registrando
também os metadados de anexos. Centraliza o envio de respostas (manuais,
sugeridas pela IA ou agendadas).
"""
import json
from datetime import datetime
from typing import List, Optional

from src import config
from src.core.ai_engine import AIService
from src.core.email_service import EmailService
from src.data import db
from src.exceptions import EmailConnectionError, EmailSendError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SupportController:
    """
    Controlador principal que orquestra o fluxo de suporte.

    Responsável por:
        - Buscar novos e-mails não lidos
        - Enviar para análise da IA
        - Salvar tickets e metadados de anexos no banco
        - Marcar e-mails como lidos
        - Enviar respostas (com anexos opcionais)
    """

    def __init__(self) -> None:
        """Inicializa o controlador com os serviços necessários."""
        self.email_api = EmailService()
        self.ai_api = AIService()
        db.init_db()
        logger.info("SupportController inicializado")

    def run_sync(self) -> int:
        """
        Executa a sincronização de e-mails.

        Busca e-mails não lidos, analisa com IA, salva tickets e anexos.

        Returns:
            Número de tickets processados.
        """
        logger.info("Iniciando sincronização de e-mails...")

        try:
            new_emails = self.email_api.fetch_unread_emails()
        except EmailConnectionError as e:
            logger.error(f"Falha na conexão: {e.message}")
            return 0

        if not new_emails:
            logger.info("Nenhum ticket novo encontrado")
            return 0

        auto_download = config.get_bool("AUTO_DOWNLOAD_ATTACHMENTS", False)
        processed = 0

        for mail in new_emails:
            if not mail.get("body"):
                logger.warning(f"E-mail sem corpo ignorado: {mail.get('subject')}")
                continue

            logger.info(f"Analisando ticket: {mail['subject']}")
            analysis = self.ai_api.analyze_ticket(mail["body"])

            ticket_data = {
                "uid": mail["id"],
                "sender": mail["sender"],
                "subject": mail["subject"],
                "body": mail["body"],
                "urgencia": analysis.get("urgencia", "Média"),
                "categoria": analysis.get("categoria", "Outros"),
                "resumo": analysis.get("resumo", "Sem resumo"),
                "resposta_sugerida": analysis.get("resposta_sugerida", ""),
            }

            ticket_id = db.save_ticket(ticket_data)
            if not ticket_id:
                continue

            self._register_attachments(ticket_id, mail.get("attachments", []), auto_download)
            self.email_api.mark_as_read(mail["id"])
            processed += 1
            logger.debug(f"Ticket salvo: {mail['id']}")

        logger.info(f"Sincronização concluída: {processed} tickets processados")
        return processed

    def send_ticket_reply(
        self,
        ticket_id: int,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """
        Envia uma resposta a um ticket e o marca como respondido/resolvido.

        Args:
            ticket_id: ID do ticket a responder.
            body: Texto da resposta.
            attachments: Caminhos de arquivos a anexar.

        Returns:
            ``True`` se enviado com sucesso.
        """
        ticket = db.get_ticket_by_id(ticket_id)
        if not ticket:
            logger.warning(f"Ticket {ticket_id} não encontrado para resposta")
            return False

        subject = f"Re: {ticket.subject}" if ticket.subject else "Re: Suporte"
        try:
            self.email_api.send_reply(ticket.sender, subject, body, attachments)
        except EmailSendError as e:
            logger.error(f"Falha ao responder ticket {ticket_id}: {e.message}")
            return False

        db.mark_ticket_responded(ticket_id)
        return True

    def process_scheduled_replies(self) -> int:
        """
        Envia as respostas agendadas cujo horário já chegou.

        Returns:
            Número de respostas enviadas com sucesso.
        """
        due = db.due_scheduled_replies(datetime.now())
        sent = 0
        for reply in due:
            attachments = json.loads(reply.attachments_json) if reply.attachments_json else []
            try:
                self.email_api.send_reply(
                    reply.to_email, reply.subject, reply.body, attachments
                )
                db.update_scheduled_reply_status(reply.id, reply.STATUS_SENT)
                db.mark_ticket_responded(reply.ticket_id)
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
            if auto_download and attachment_id:
                attachment_manager.download_attachment(attachment_id)
