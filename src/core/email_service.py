"""
Serviço de integração com e-mail (IMAP para leitura, SMTP para envio).

Responsável por:
    - Buscar e-mails não lidos (com metadados de anexos)
    - Marcar e-mails como lidos
    - Baixar o conteúdo de um anexo específico sob demanda
    - Enviar respostas (com anexos opcionais) via SMTP

As credenciais e servidores são resolvidos via :mod:`src.config`, podendo ser
configurados pela interface web ou por variáveis de ambiente.
"""
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from imap_tools import AND, MailBox

from src import config
from src.exceptions import EmailConnectionError, EmailSendError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """
    Serviço de acesso a e-mails via IMAP/SMTP.

    Suporta Gmail e Outlook por padrão; outros provedores podem ser usados
    configurando os servidores manualmente.
    """

    def __init__(self) -> None:
        """Carrega credenciais e servidores a partir da configuração."""
        self.user = config.get("EMAIL_USER")
        self.password = config.get("EMAIL_PASS")
        self.imap_server = config.get("IMAP_SERVER", "imap.gmail.com")
        self.smtp_server = config.get("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = config.get_int("SMTP_PORT", 587)

        if not self.user or not self.password:
            logger.warning("Credenciais de e-mail não configuradas")
        logger.debug(f"EmailService inicializado para {self.user}")

    # ------------------------------------------------------------------
    # Leitura (IMAP)
    # ------------------------------------------------------------------
    def fetch_unread_emails(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca e-mails não lidos da caixa de entrada.

        Args:
            limit: Número máximo de e-mails a buscar.

        Returns:
            Lista de dicionários com ``id``, ``sender``, ``subject``, ``body``,
            ``date`` e ``attachments`` (lista de metadados).

        Raises:
            EmailConnectionError: Se falhar a conexão com o servidor.
        """
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
                            "attachments": self._extract_attachment_meta(msg),
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
        """Marca um e-mail como lido. Retorna ``True`` se bem-sucedido."""
        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                mailbox.flag(uid, "\\Seen", True)
            logger.debug(f"E-mail {uid} marcado como lido")
            return True
        except Exception as e:
            logger.error(f"Erro ao marcar e-mail como lido: {e}")
            return False

    def download_attachment(self, uid: str, filename: str) -> Optional[bytes]:
        """
        Baixa o conteúdo binário de um anexo específico sob demanda.

        Args:
            uid: UID IMAP do e-mail.
            filename: Nome do arquivo do anexo desejado.

        Returns:
            Bytes do anexo, ou ``None`` se não encontrado.
        """
        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(AND(uid=uid)):
                    for att in msg.attachments:
                        if att.filename == filename:
                            return att.payload
            logger.warning(f"Anexo '{filename}' não encontrado no e-mail {uid}")
            return None
        except Exception as e:
            logger.error(f"Erro ao baixar anexo: {e}")
            return None

    # ------------------------------------------------------------------
    # Envio (SMTP)
    # ------------------------------------------------------------------
    def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """
        Envia uma resposta por e-mail, com anexos opcionais.

        Args:
            to_email: Destinatário.
            subject: Assunto.
            body: Corpo da mensagem (texto).
            attachments: Lista de caminhos de arquivos a anexar.

        Returns:
            ``True`` se enviado com sucesso.

        Raises:
            EmailSendError: Se o envio falhar.
        """
        if not self.user or not self.password:
            raise EmailSendError(message="Credenciais de e-mail não configuradas")

        message = EmailMessage()
        message["From"] = self.user
        message["To"] = to_email
        message["Subject"] = subject or "Re: Suporte"
        message.set_content(body)

        for path in attachments or []:
            self._attach_file(message, path)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(message)
            logger.info(f"Resposta enviada para {to_email}")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail: {e}")
            raise EmailSendError(message="Falha ao enviar e-mail", details=str(e))

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_attachment_meta(msg: Any) -> List[Dict[str, Any]]:
        """
        Extrai metadados (não o conteúdo) dos anexos de uma mensagem.

        Defensivo: tolera mensagens sem o atributo ``attachments`` ou com
        formatos inesperados (importante em testes com mocks).
        """
        attachments = getattr(msg, "attachments", None)
        if not isinstance(attachments, (list, tuple)):
            return []
        meta: List[Dict[str, Any]] = []
        for att in attachments:
            try:
                meta.append(
                    {
                        "filename": att.filename,
                        "content_type": att.content_type,
                        "size": len(att.payload) if att.payload else 0,
                    }
                )
            except Exception:  # pragma: no cover - anexo malformado
                continue
        return meta

    @staticmethod
    def _attach_file(message: EmailMessage, path: str) -> None:
        """Anexa um arquivo local à mensagem, ignorando erros de leitura."""
        import mimetypes
        import os

        if not path or not os.path.isfile(path):
            logger.warning(f"Anexo ignorado (não encontrado): {path}")
            return
        ctype, _ = mimetypes.guess_type(path)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        with open(path, "rb") as f:
            message.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=os.path.basename(path),
            )
