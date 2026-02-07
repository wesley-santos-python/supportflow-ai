"""
Serviço de integração com e-mail via IMAP.

Responsável por buscar e-mails não lidos e marcar como lidos após processamento.
"""
import os
from typing import List, Dict, Any

from imap_tools import MailBox, AND
from dotenv import load_dotenv

from src.utils.logger import get_logger
from src.exceptions import EmailConnectionError

load_dotenv()
logger = get_logger(__name__)


class EmailService:
    """
    Serviço de acesso a e-mails via protocolo IMAP.
    
    Suporta Gmail e Outlook. Configuração via variáveis de ambiente.
    
    Attributes:
        user: Endereço de e-mail do usuário.
        password: Senha de app para autenticação.
        imap_server: Servidor IMAP (default: imap.gmail.com).
    """
    
    IMAP_SERVERS = {
        "gmail": "imap.gmail.com",
        "outlook": "outlook.office365.com",
    }
    
    def __init__(self) -> None:
        """Inicializa o serviço com credenciais do ambiente."""
        self.user = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASS")
        self.imap_server = os.getenv("IMAP_SERVER", self.IMAP_SERVERS["gmail"])
        
        if not self.user or not self.password:
            logger.warning("Credenciais de e-mail não configuradas")
        
        logger.debug(f"EmailService inicializado para {self.user}")

    def fetch_unread_emails(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca e-mails não lidos da caixa de entrada.
        
        Args:
            limit: Número máximo de e-mails a buscar.
        
        Returns:
            Lista de dicionários com id, sender, subject, body e date.
        
        Raises:
            EmailConnectionError: Se falhar a conexão com o servidor.
        """
        emails_payload: List[Dict[str, Any]] = []
        
        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                    emails_payload.append({
                        "id": msg.uid,
                        "sender": msg.from_,
                        "subject": msg.subject,
                        "body": msg.text,
                        "date": msg.date
                    })
            
            logger.info(f"Buscados {len(emails_payload)} e-mails não lidos")
            return emails_payload
            
        except Exception as e:
            logger.error(f"Erro ao acessar e-mail: {e}")
            raise EmailConnectionError(
                message="Falha ao conectar com servidor de e-mail",
                details=str(e)
            )

    def mark_as_read(self, uid: str) -> bool:
        """
        Marca um e-mail como lido.
        
        Args:
            uid: ID único do e-mail (IMAP UID).
        
        Returns:
            True se marcado com sucesso, False caso contrário.
        """
        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                mailbox.flag(uid, '\\Seen', True)
            logger.debug(f"E-mail {uid} marcado como lido")
            return True
        except Exception as e:
            logger.error(f"Erro ao marcar e-mail como lido: {e}")
            return False