"""
Serviço de integração com e-mail (IMAP para leitura, SMTP para envio).

Responsável por:
    - Buscar e-mails não lidos (com metadados de anexos)
    - Marcar e-mails como lidos
    - Baixar o conteúdo de um anexo específico sob demanda
    - Enviar respostas (com anexos opcionais) via SMTP

As credenciais e servidores vêm de um provedor de configuração — pode ser o
módulo global :mod:`src.config` (env/variáveis) ou uma
:class:`~src.user_config.UserConfig` escopada a um cliente (multi-tenant).
"""
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from imap_tools import AND, MailBox

from src import config
from src.exceptions import EmailConnectionError, EmailSendError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Mensagem usada quando não há credenciais legíveis (não configurado ou a
# senha salva ficou ilegível porque o SECRET_KEY do servidor mudou).
_RESAVE_MSG = (
    "E-mail não configurado, ou a senha salva expirou porque a chave de "
    "segurança (SECRET_KEY) do servidor mudou. Abra Configurações e salve a "
    "senha de app novamente."
)


class EmailService:
    """
    Serviço de acesso a e-mails via IMAP/SMTP.

    Suporta Gmail e Outlook por padrão; outros provedores podem ser usados
    configurando os servidores manualmente.
    """

    def __init__(self, cfg: Any = None) -> None:
        """
        Carrega credenciais e servidores a partir de um provedor de config.

        Args:
            cfg: Provedor com interface ``get``/``get_int`` (ex.: ``UserConfig``).
                 Se ``None``, usa a configuração global (env) — modo single-tenant.
        """
        cfg = cfg or config
        self._cfg = cfg
        self.user = cfg.get("EMAIL_USER")
        self.password = cfg.get("EMAIL_PASS")
        self.imap_server = cfg.get("IMAP_SERVER", "imap.gmail.com")
        self.smtp_server = cfg.get("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = cfg.get_int("SMTP_PORT", 587)

        if not self.user or not self.password:
            logger.warning("Credenciais de e-mail não configuradas")
        logger.debug(f"EmailService inicializado para {self.user}")

    # ------------------------------------------------------------------
    # Leitura (IMAP)
    # ------------------------------------------------------------------
    def fetch_unread_emails(self, limit: int = 10, since_days: int = None) -> List[Dict[str, Any]]:
        """
        Busca e-mails não lidos da caixa de entrada.

        Args:
            limit: Número máximo de e-mails a buscar.
            since_days: Se informado, considera apenas e-mails dos últimos N dias
                (usado na 1ª sincronização para não varrer um backlog antigo).

        Returns:
            Lista de dicionários com ``id``, ``sender``, ``subject``, ``body``,
            ``date`` e ``attachments`` (lista de metadados).

        Raises:
            EmailConnectionError: Se falhar a conexão com o servidor.
        """
        emails_payload: List[Dict[str, Any]] = []

        if not self.user or not self.password:
            raise EmailConnectionError(message=_RESAVE_MSG)

        criteria = {"seen": False}
        if since_days:
            from datetime import date, timedelta

            criteria["date_gte"] = date.today() - timedelta(days=since_days)

        try:
            with MailBox(self.imap_server).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(AND(**criteria), limit=limit, reverse=True):
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
                message=_friendly_imap_error(e, self.imap_server),
                details=str(e),
            )

    def test_connection(self) -> None:
        """
        Verifica as credenciais autenticando no servidor IMAP.

        Raises:
            EmailConnectionError: com mensagem amigável explicando o motivo
                (senha de app incorreta, servidor inacessível, etc.).
        """
        if not self.user or not self.password:
            raise EmailConnectionError(
                message="Informe o e-mail e a senha de app antes de testar."
            )
        try:
            with MailBox(self.imap_server).login(self.user, self.password):
                pass
        except Exception as e:
            logger.error(f"Teste de conexão de e-mail falhou: {e}")
            raise EmailConnectionError(
                message=_friendly_imap_error(e, self.imap_server),
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
            raise EmailSendError(message=_RESAVE_MSG)

        message = EmailMessage()
        message["From"] = self.user
        message["To"] = to_email
        message["Subject"] = subject or "Re: Suporte"
        message.set_content(body)

        # Versão HTML (template escolhido) como alternativa, salvo se o cliente
        # preferir e-mail em texto puro (EMAIL_FORMAT="plain").
        if str(self._cfg.get("EMAIL_FORMAT") or "html").lower() != "plain":
            from src.core.email_templates import branding_from_cfg, render_email

            try:
                html_body = render_email(body, branding_from_cfg(self._cfg))
                message.add_alternative(html_body, subtype="html")
            except Exception as exc:  # pragma: no cover - degrada para texto
                logger.warning(f"Falha ao renderizar HTML, enviando texto: {exc}")

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
            raise EmailSendError(message=_friendly_imap_error(e, self.smtp_server), details=str(e))

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


def _friendly_imap_error(exc: Exception, imap_server: str) -> str:
    """
    Traduz um erro de IMAP em uma mensagem clara em português para o usuário.

    A causa mais comum no Gmail é usar a senha normal da conta em vez de uma
    "senha de app" — então essa orientação é destacada.
    """
    raw = str(exc).lower()
    auth_keys = ("auth", "credential", "invalid", "login failed", "password", "username", "[alert]")
    net_keys = ("getaddrinfo", "name or service", "resolve", "timed out", "timeout",
                "connection", "refused", "unreachable", "ssl")

    # Usuário/senha vazios = credencial ilegível (SECRET_KEY mudou) ou não salva.
    if "empty username or password" in raw:
        return _RESAVE_MSG
    if any(k in raw for k in auth_keys):
        return (
            "E-mail ou senha incorretos. No Gmail, ative a verificação em duas "
            "etapas e use uma SENHA DE APP (myaccount.google.com/apppasswords) — "
            "não a senha normal da conta."
        )
    if any(k in raw for k in net_keys):
        return (
            f"Não foi possível conectar ao servidor IMAP ({imap_server}). "
            "Verifique o servidor e a porta nas configurações."
        )
    return f"Falha ao conectar com o servidor de e-mail: {exc}"
