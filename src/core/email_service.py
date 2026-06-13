"""
Serviço de integração com e-mail via IMAP.

Responsável por buscar e-mails não lidos e marcar como lidos após processamento.
"""
from typing import Any, Dict, Iterable, List

from imap_tools import AND, MailBox

from src.config import settings
from src.exceptions import EmailConnectionError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """
    Serviço de acesso a e-mails via protocolo IMAP.

    Suporta Gmail e Outlook. Configuração via variáveis de ambiente.
    """

    def __init__(self) -> None:
        """Inicializa o serviço com credenciais da configuração."""
        self.user = settings.email_user
        self.password = settings.email_pass
        self.imap_server = settings.imap_server

        if not settings.email_configured:
            logger.warning("Credenciais de e-mail não configuradas")

        logger.debug(f"EmailService inicializado para {self.user}")

    def fetch_unread_emails(self, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Busca e-mails não lidos da caixa de entrada.

        Args:
            limit: Número máximo de e-mails (default: FETCH_LIMIT do ambiente).

        Returns:
            Lista de dicionários com id, sender, subject, body e date.

        Raises:
            EmailConnectionError: Se falhar a conexão com o servidor.
        """
        limit = limit or settings.fetch_limit
        emails_payload: List[Dict[str, Any]] = []

        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                    emails_payload.append(
                        {
                            "id": msg.uid,
                            "sender": msg.from_,
                            "subject": msg.subject,
                            "body": msg.text,
                            "date": msg.date,
                        }
                    )

            logger.info(f"Buscados {len(emails_payload)} e-mails não lidos")
            return emails_payload

        except Exception as e:
            logger.error(f"Erro ao acessar e-mail: {e}")
            raise EmailConnectionError(
                message="Falha ao conectar com servidor de e-mail",
                details=str(e),
            )

    def mark_as_read(self, uid: str) -> bool:
        """Marca um único e-mail como lido."""
        return self.mark_as_read_bulk([uid])

    def mark_as_read_bulk(self, uids: Iterable[str]) -> bool:
        """
        Marca vários e-mails como lidos em uma única conexão IMAP.

        Args:
            uids: IDs únicos (IMAP UID) dos e-mails.

        Returns:
            True se a operação foi bem-sucedida, False caso contrário.
        """
        uid_list = [u for u in uids if u]
        if not uid_list:
            return True
        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                mailbox.flag(uid_list, "\\Seen", True)
            logger.debug(f"{len(uid_list)} e-mail(s) marcado(s) como lido(s)")
            return True
        except Exception as e:
            logger.error(f"Erro ao marcar e-mails como lidos: {e}")
            return False
