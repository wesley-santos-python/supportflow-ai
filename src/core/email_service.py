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
import base64
import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from imap_tools import AND, MailBox

from src import config
from src.exceptions import EmailConnectionError, EmailSendError
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _clean_header(value: Optional[str]) -> str:
    """
    Remove quebras de linha (CR/LF) de um valor de cabeçalho de e-mail.

    Cabeçalhos como ``Subject``/``To`` NÃO podem conter ``\\n`` ou ``\\r`` —
    o ``smtplib`` levanta "Header values may not contain linefeed or carriage
    return characters" e o envio falha. Assuntos de e-mails recebidos podem vir
    com quebras embutidas (ex.: notificações do GitHub), então colapsamos
    qualquer CR/LF em um espaço antes de montar a mensagem.
    """
    if not value:
        return ""
    return " ".join(str(value).replace("\r", "\n").split("\n")).strip()


def _friendly_resend_error(status: int, detail: str) -> str:
    """Traduz erros comuns da API do Resend em mensagens claras para a UI."""
    low = (detail or "").lower()
    # Domínio não verificado costuma vir como HTTP 403 — checado ANTES do
    # status para não ser ofuscado pela mensagem genérica de "API key inválida".
    if "domain" in low or "not verified" in low:
        return (
            "O domínio do remetente não está verificado no Resend. Verifique o "
            "domínio em RESEND_FROM (ex.: floatech.app) no painel do Resend."
        )
    if status == 401 or "api key" in low or "unauthorized" in low:
        return (
            "A chave do Resend (RESEND_API_KEY) é inválida ou expirou. "
            "Gere uma nova no painel do Resend e atualize as Variables do Railway."
        )
    if status == 403:
        return (
            "O serviço de envio (Resend) recusou a autorização. Confira se a "
            "RESEND_API_KEY tem permissão de envio e se o domínio em RESEND_FROM "
            "está verificado no painel do Resend."
        )
    if status == 422:
        return f"E-mail recusado pelo serviço de envio: {detail}"
    if status == 429:
        return "Limite de envios do Resend atingido. Tente novamente mais tarde."
    return f"Falha no serviço de envio (Resend, HTTP {status})."


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
            with MailBox(self.imap_server, timeout=25).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(AND(**criteria), limit=limit, reverse=True):
                    emails_payload.append(
                        {
                            "id": msg.uid,
                            "sender": msg.from_,
                            "subject": msg.subject,
                            "body": msg.text,
                            "html": msg.html,
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
            with MailBox(self.imap_server, timeout=25).login(self.user, self.password):
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
            with MailBox(self.imap_server, timeout=25).login(self.user, self.password) as mailbox:
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
            with MailBox(self.imap_server, timeout=25).login(self.user, self.password) as mailbox:
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
        clean_subject = _clean_header(subject) or "Re: Suporte"
        clean_to = _clean_header(to_email)

        # Versão HTML (template escolhido), salvo se o cliente preferir texto
        # puro (EMAIL_FORMAT="plain"). Vale para os dois caminhos de envio.
        html_body = None
        if str(self._cfg.get("EMAIL_FORMAT") or "html").lower() != "plain":
            from src.core.email_templates import branding_from_cfg, render_email

            try:
                html_body = render_email(body, branding_from_cfg(self._cfg))
            except Exception as exc:  # pragma: no cover - degrada para texto
                logger.warning(f"Falha ao renderizar HTML, enviando texto: {exc}")

        # Caminho preferido: API HTTP do Resend (porta 443). Resolve o bloqueio
        # de SMTP de saída do Railway e funciona para TODOS os clientes através
        # de uma única conta central (RESEND_API_KEY nas Variables do Railway).
        # O remetente é o domínio verificado (RESEND_FROM); o Reply-To é o
        # e-mail do próprio cliente, então a resposta do cliente final cai na
        # caixa dele.
        resend_key = config.get("RESEND_API_KEY")
        if resend_key:
            return self._send_via_resend(
                api_key=resend_key,
                to_email=clean_to,
                subject=clean_subject,
                text_body=body,
                html_body=html_body,
                reply_to=_clean_header(self.user),
                attachments=attachments,
            )

        # Caminho legado (dev/local, ou quem ainda usa SMTP próprio).
        if not self.user or not self.password:
            raise EmailSendError(message=_RESAVE_MSG)

        message = EmailMessage()
        message["From"] = _clean_header(self.user)
        message["To"] = clean_to
        message["Subject"] = clean_subject
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        for path in attachments or []:
            self._attach_file(message, path)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=25) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(message)
            logger.info(f"Resposta enviada para {to_email}")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail: {e}")
            raise EmailSendError(message=_friendly_imap_error(e, self.smtp_server), details=str(e))

    def _send_via_resend(
        self,
        api_key: str,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str],
        reply_to: Optional[str],
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """Envia a resposta pela API HTTP do Resend (https://resend.com)."""
        from_addr = (
            config.get("RESEND_FROM")
            or "Suporte Floatech <atendimento@floatech.app>"
        )
        payload: Dict[str, Any] = {
            "from": from_addr,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
        }
        if html_body:
            payload["html"] = html_body
        if reply_to:
            payload["reply_to"] = reply_to
        else:
            # Sem Reply-To a resposta do cliente final cairia na conta central
            # (RESEND_FROM) em vez da caixa do cliente. Avisa para não falhar
            # silenciosamente quando o EMAIL_USER do cliente não está definido.
            logger.warning(
                "Envio via Resend sem Reply-To (EMAIL_USER do cliente ausente): "
                "respostas do destinatário irão para o remetente central."
            )

        files = []
        for path in attachments or []:
            if not path or not os.path.isfile(path):
                logger.warning(f"Anexo ignorado (não encontrado): {path}")
                continue
            try:
                with open(path, "rb") as fh:
                    content = base64.b64encode(fh.read()).decode("ascii")
                files.append({"filename": os.path.basename(path), "content": content})
            except OSError as exc:  # pragma: no cover - anexo sumiu do disco
                logger.warning(f"Anexo ignorado ({path}): {exc}")
        if files:
            payload["attachments"] = files

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as resp:
                resp.read()
            logger.info(f"Resposta enviada via Resend para {to_email}")
            return True
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace") if exc.fp else str(exc)
            logger.error(f"Erro Resend ({exc.code}): {detail}")
            raise EmailSendError(
                message=_friendly_resend_error(exc.code, detail), details=detail
            )
        except Exception as exc:
            logger.error(f"Erro ao enviar via Resend: {exc}")
            raise EmailSendError(
                message="Falha ao enviar o e-mail pelo serviço de envio (Resend). "
                "Tente novamente em instantes.",
                details=str(exc),
            )

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
