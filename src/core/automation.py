"""
Controlador de automação do SupportFlow AI.

Orquestra o fluxo de sincronização: e-mail -> IA -> banco de dados.
"""
from src.core.ai_engine import AIService
from src.core.email_service import EmailService
from src.data.db import create_ticket, init_db, session_scope, ticket_exists
from src.exceptions import EmailConnectionError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SupportController:
    """
    Controlador principal que orquestra o fluxo de suporte.

    Responsável por:
    - Buscar novos e-mails não lidos;
    - Pular e-mails já processados (sem gastar chamadas de IA);
    - Enviar novos e-mails para análise da IA;
    - Salvar tickets no banco de dados;
    - Marcar e-mails processados como lidos (em lote).
    """

    def __init__(self) -> None:
        """Inicializa o controlador com os serviços necessários."""
        self.email_api = EmailService()
        self.ai_api = AIService()
        init_db()
        logger.info("SupportController inicializado")

    def run_sync(self) -> int:
        """
        Executa a sincronização de e-mails.

        Returns:
            Número de tickets novos processados.
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

        processed_uids: list[str] = []

        with session_scope() as db:
            for mail in new_emails:
                uid = mail["id"]

                if not mail["body"]:
                    logger.warning(f"E-mail sem corpo ignorado: {mail['subject']}")
                    continue

                # Dedupe ANTES de chamar a IA — evita custo desnecessário.
                if ticket_exists(db, uid):
                    logger.debug(f"E-mail já processado, ignorado: {uid}")
                    processed_uids.append(uid)
                    continue

                logger.info(f"Analisando ticket: {mail['subject']}")
                analysis = self.ai_api.analyze_ticket(mail["body"])

                ticket_data = {
                    "uid": uid,
                    "sender": mail["sender"],
                    "subject": mail["subject"],
                    "body": mail["body"],
                    "urgencia": analysis.get("urgencia", "Média"),
                    "categoria": analysis.get("categoria", "Outros"),
                    "resumo": analysis.get("resumo", "Sem resumo"),
                    "resposta_sugerida": analysis.get("resposta_sugerida", ""),
                }

                if create_ticket(db, ticket_data):
                    processed_uids.append(uid)
                    logger.debug(f"Ticket salvo: {uid}")

        # Marca todos os processados como lidos em uma única conexão IMAP.
        if processed_uids:
            self.email_api.mark_as_read_bulk(processed_uids)

        logger.info(f"Sincronização concluída: {len(processed_uids)} e-mail(s)")
        return len(processed_uids)
